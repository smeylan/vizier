import requests
import utils 
import pytz
import datetime
from datetime import datetime as dt
from dateutil.parser import parse
import config

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


def scheduledEventHandler(args, fb, emailer):
	''' API endpoint that allows a trigger to call processEvent on scheduled events'''
	vizierUserId, vizierStudyId, vizierEventId = utils.extractOrComplain(args, ['vizierUserId', 'vizierStudyId', 'vizierEventId']) 

	# retrieve the event from Firebase
	vizierSegmentId = vizierEventId.split('_')[0]
	
	vizierSegment = fb.reference('studies/'+vizierStudyId+'/'+vizierSegmentId).get()

	response = processEvent(vizierUserId, vizierStudyId, vizierSegment['followup_events'][vizierEventId], fb, emailer)
	return(response)	
    

def processEvent(vizierUserId, vizierStudyId, vizierEvent, fb, emailer):
	'''adjudicate between specific event logic on the basis of event type'''	

	if vizierEvent['event_type'] == 'email':	
		response = processEvent_email(vizierUserId, vizierStudyId, vizierEvent, fb, emailer)

	elif vizierEvent['event_type'] == 'api':
		response = processEvent_API(vizierUserId, vizierStudyId, vizierEvent, fb)			
	else:
		raise NotImplementedError	

	return(response)


def processEvent_email(vizierUserId, vizierStudyId, vizierEvent, fb, emailer):
	'''send an email'''	
	
	# get the properties of the user to pull out recipient email
	user = fb.reference('users/'+vizierUserId).get()	

	if 'email' not in user:
		return({'error':'noEmailForParticipant'})
	else:
		recipient_email = user['email']


	# get the relevant email content from the email node. "email_id" is a unique identidier for the copy for the email		
	email = fb.reference('/emails/'+vizierEvent['email_id']).get()
	if email is None:
		return({'error':'emailTemplateNotFound'})

	# email must have 'subject' and 'body'
	body = email['body']
	subject = email['subject']	
	
	# Update subject and body  

	# "user_vars: is a dict with a map of variable names to keys in users/payload. Appopriate in order to get variables from the user node in Firebase
	for search,key in vizierEvent['user_vars'].items():
		if key in user:
			replace = user[key]
		else:
			return({"error":"userKeyMissingForEmail"})
		
		body = body.replace('$'+search.upper(), replace)
		subject = subject.replace('$'+search.upper(), replace)

	# "string_vars" is a simple key-value pair. Appropriate in order to get variables from the study node in Firebase
	for search,replace in vizierEvent['string_vars'].items():				
		body = body.replace('$'+search.upper(), replace)
		subject = subject.replace('$'+search.upper(), replace)

	emailer.send_message(subject=subject,body=body,recipient=recipient_email)	

	return({'success':1})

def processEvent_API(vizierUserId, vizierStudyId, vizierEvent, fb):
	'''hit an API'''
	# "url" is the URL of the API endpoint to hit
	if 'url' not in vizierEvent:
		return({'error': 'urlNotDefined'})             
	
	if 'method' not in vizierEvent: 
		method = 'post'

	post_body = {}
	
	# "user_vars": is a dict with a map of variable names to keys in users/payload. processEvent interprets this so that the POST body with include 'key':users['payload'][value]
	
	if 'user_vars' in vizierEvent:
		user_vars = fb.reference('users/'+vizierUserId+'/user_vars').get()
		for key, value in vizierEvent['user_vars'].items():
			post_body[key] = user_vars[value]		

	# "json_string": key and value are both added verbatim to the POST JSON body, 'key':'value'
	if 'string_vars' in vizierEvent:
		for key, value in vizierEvent['string_vars'].items():
			if key not in user_vars:
				post_body[key] = value
			else:
				print('Preventing string_var from overwriting existing user_var')					

	
	# make the request
	if method == 'post':
		resp = requests.post(vizierEvent['url'], data=post_body)  
	elif method == 'get':
		resp = requests.get(vizierEvent['url'], data=post_body)  
	else: 
		return({'error':'methodNotRecognized'})

	# stub: do we want to do something with the response (resp)? -- either to update the state or to confirm success

	return({'success':1})

def scheduleEvent(vizierUserId, vizierStudyId, vizierEvent, fb, scheduler):
	'''Add an event to be run in the future, stored as an APscheduler job. When the time is up, hit the trigger, which generates an API call. Thus all future events are processed by the same infrastructure used to hadle events now'''
	#(vizier event = apscheduler job)

	job_list = [x.id for x in scheduler.get_jobs()]

	# compose a unique job name 
	job_name = vizierUserId+'_'+vizierStudyId+'_'+vizierEvent['eventId']

	# compute the date using the date string
	schedule_string = vizierEvent['schedule']

	
	# get the user's creation time in utc
	vizierUser = fb.reference('users/'+vizierUserId).get()
	user_tz_string = vizierUser['timezone']
	started_study_dt = parse(vizierUser['createdAtLocal'])
	current_dt = utils.now(vizierUser['timezone'],returnString=False)

	event_utc_dt = translateScheduleString(schedule_string, started_study_dt, current_dt, user_tz_string)

	# check if that event name is in the scheduler (message_list)
	if job_name in job_list:
		return({'error':'alreadyScheduled'})
	else:
		# if not, add it
		scheduler.add_job(id=job_name, func=scheduledEventTrigger, trigger='date', run_date= event_utc_dt, args = [vizierUserId, vizierStudyId, vizierEvent['eventId']], misfire_grace_time= 120)
	return({"success":1})

def cancelEvents(vizierUserId, vizierStudyId, current_segmentId, scheduler):
	'''cancel events in the scheduler either for a user, or for a specific segment for a user (for example, when they have advanced to the next segment)'''
	
	job_list = [x.id for x in scheduler.get_jobs()]
	
	if current_segmentId is None:	
		#cancel all events for this user
		for job in job_list:
			if job.split('_')[0] == vizierUserId:
				scheduler.remove_job(job_id=job)  
	else: 
		# cancel all jobs with current_segmentID
		for job in job_list:
			if job.split('_')[0] == vizierUserId:
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
	
