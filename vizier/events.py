import requests
import utils 
import pytz
from datetime import datetime as dt
from dateutil.parser import parse

def scheduledEventTrigger(userId, studyId, eventId):
	'''when a scheduled event happens in apscheduler, it hits this function, which generates an API call to the handler'''
	url = config.BASE_URL+'scheduledEventHandler'
	post_body = {
		"userId": userId,
		"studyId": studyId,
		"eventId": eventId
	}
	resp = requests.post(url, data= post_body)  
  	return(resp.text)


def scheduledEventHandler(args):
	''' API endpoint that allows a trigger to call processEvent on scheduled events'''
	vizierUserId, vizierStudyId, vizierEventId = utils.extractOrComplain(args, ['vizierUserId', 'vizierStudyId', 'vizierEventId']) 

	# retrieve the event from Firebase
	vizierSegmentId = vizierEventId.split('_')[0]
	
	vizierSegment = fb.reference('studies/'+vizierStudyId+'/'+vizierSegmentId).get()

	response = processEvent(vizierUserId, vizierStudyId, vizierSegment['followup_events'][vizierEventId])
	return(response)	
    

def processEvent(vizierUserId, vizierStudyId, vizierEvent):
	'''adjudicate between specific event logic on the basis of event type'''	

	if vizierEvent['event_type'] == 'email':	
		response = processEvent_email(vizierUserId, vizierStudyId, vizierEvent)

	elif vizierEvent['event_type'] == 'api':
		response = processEvent_API(vizierUserId, vizierStudyId, vizierEvent)			
	else:
		raise NotImplementedError	

	return(response)


def processEvent_email(userId, studyId, event):
	'''send an email'''

	# "email_id" is a unique identidier for the copy for the email		
	# "user_vars: is a dict with a map of variable names to keys in users/payload
	# "string_vars" is a simple key-value pair
	raise NotImplementedError

def processEvent_API(userId, studyId, event):
	'''hit an API'''
	# "url" is the URL of the API endpoint to hit
	if 'url' not in event:
		return({'error': 'urlNotDefined'})             
	
	if 'method' not in event: 
		method = 'post'

	post_body = {}
	
	# "user_vars": is a dict with a map of variable names to keys in users/payload. processEvent interprets this so that the POST body with include 'key':users['payload'][value]
	
	if 'user_vars' in event:
		user_vars = fb.reference('users/'+userId+'/user_vars').get()
		for key, value in event['user_vars'].items():
			post_body[key] = user_vars[value]		

	# "json_string": key and value are both added verbatim to the POST JSON body, 'key':'value'
	if 'string_vars' in event:
		for key, value in event['string_vars'].items():
			if key not in user_vars:
				post_body[key] = value
			else:
				print('Preventing string_var from overwriting existing user_var')					

	
	# make the request
	if method == 'post':
		resp = requests.post(url, data=post_body)  
	elif method == 'get':
		resp = requests.get(url, data=post_body)  
	else: 
		return({'error':'methodNotRecognized'})

	return({'success':1})

def scheduleEvent(userId, studyId, event, scheduler):
	'''Add an event to be run in the future, stored as an APscheduler job. When the time is up, hit the trigger, which generates an API call. Thus all future events are processed by the same infrastructure used to hadle events now'''
	#(vizier event = apscheduler job)

	job_list = [x.id for x in scheduler.get_jobs()]

	# compose a unique job name 
	job_name = userId+'_'+studyId+'_'+event['eventId']

	# compute the date using the date string
	schedule_string = event['event_schedule']

	
	# get the user's creation time in utc
	user = fb.reference('users/'+userId).get()
	started_study_dt = parse(user['createdAtLocal'])
	current_dt = utils.now(user['timezone'],returnString=False)

	event_utc_dt = translateScheduleString(schedule_string, started_study_dt, current_dt, user_tz_string)

	# check if that event name is in the scheduler (message_list)
	if job_name in job_list:
		return({'error':'alreadyScheduled'})
	else:
		# if not, add it
		scheduler.add_job(id=job_name, func=processEventTrigger, trigger='date', run_date= event_utc_dt, args = [userId, studyId, event['eventId']], misfire_grace_time= 120)

def cancelEvents(userId, studyId, current_segmentId, scheduler):
	'''cancel events in the scheduler either for a user, or for a specific segment for a user (for example, when they have advanced to the next segment)'''
	
	job_list = [x.id for x in scheduler.get_jobs()]
	
	if segmentId is None:	
		#cancel all events for this user
		for job in job_list:
			if job.split('_')[0] == userId:
				scheduler.remove_job(job_id=job)  
	else: 
		# cancel all jobs with current_segmentID
		for job in job_list:
			if job.split('_')[0] == userId:
				if job.split('_')[2] == current_segmentId:
					scheduler.remove_job(job_id=job)  


def translateScheduleString(schedule_string, started_study_dt, current_dt, user_tz_string):
	'''translates an abstract date representation into a real datetime.
	Abstract representations are of the form x_y@z
	x is the type: either r (releative to start of study), (c) relative to the birth of the child
	y is the number of days after the above point
	z is the local time on a 24 hour clock to send to present to the user. Minutes may be specifed after in the form x_y@z:m
  	'''
	event_type, event_time_spec = schedule_string.split('_')
  
	if event_type in ('r', 'e'):
		offset, time_to_deploy = event_time_spec.split('@')
		offset = int(offset)
		if ':' in time_to_deploy:
			hours = int(time_to_deploy.split(':')[0])
			minutes = int(time_to_deploy.split(':')[1])
		else: 
			hours = int(time_to_deploy)
	elif event_type in ('a'):
		pass # event_time_spec contains the date

	tz = pytz.timezone(user_tz_string)    
  
	if event_type == 'r':
		# relative to the start of the study
		if 'minutes' in locals():
			local_time_to_send = dt.combine(started_study_dt + datetime.timedelta(days=offset), dt.min.time()).replace(hour=hours, minute=minutes)
		else:
			local_time_to_send = dt.combine(started_study_dt + datetime.timedelta(days=offset), dt.min.time()).replace(hour=hours)      
		local_time_to_send = tz.localize(local_time_to_send, is_dst=None) 

	elif event_type == 'e':
		# relative to right now   
		if 'minutes' in locals():
			local_time_to_send = dt.combine(current_dt + datetime.timedelta(days=offset), dt.min.time()).replace(hour=hours, minute=minutes)      
		else:
			local_time_to_send = dt.combine(current_dt + datetime.timedelta(days=offset), dt.min.time()).replace(hour=hours)      
			local_time_to_send = tz.localize(local_time_to_send, is_dst=None) 

	elif event_type == 'a':
		# absolute time, e.g. "a_2017-12-11 12:00:00 PST"
		tzoffsets = {'PST': dateutil.tz.gettz('America/Los_Angeles'),'EST': dateutil.tz.gettz('America/New_York')}
		local_time_to_send = parse(event_time_spec, tzinfos=tzoffsets)
  
	return(local_time_to_send)
	
