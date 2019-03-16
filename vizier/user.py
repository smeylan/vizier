import utils 
import events
import pytz
import json


def addUser(args, fb, emailer, scheduler):
	'''instantiate a user in Vizier with a studyId and an arbitrary payload''' 
	vizierStudyId, payload = utils.extractOrComplain(args, ['vizierStudyId','payload'])

	payload = json.loads(payload.replace("'", '"'))

	# get the study for this user
	studyForUser = fb.reference('studies/'+vizierStudyId).get()
	current_segment = studyForUser[studyForUser['START']]

	if 'timezone' in payload:
		tz = payload['timezone']
	else:
		# default to EST
		tz = "America/New_York"	

	
	if 'identifier' in payload:
		# payload['identifier'] is the field name
		# payload[payload['identifier']] is a value in the payload corresponding to the specified column
		existingUser = fb.reference('users').order_by_child(payload['identifier']).equal_to(payload[payload['identifier']]).get()

		if len(existingUser) > 0:
			return({'error':'userAlreadyExists'}) 


	#instantiate in Firebase, get back the new key name
	vizierUser = fb.reference('users/').push(
		{
			"vizierStudyId": vizierStudyId,
			"segment": studyForUser['START'],
			"user_vars": payload,
			"email": payload['email'],
			"createdAtLocal": utils.now(tz),
			"timezone": tz
		}
	)
	vizierUserId = vizierUser.key	

	# process any immediate events
	for event in current_segment["immediate_events"]:
		response = events.processEvent(vizierUserId, vizierStudyId, event, fb, emailer)		

		if 'success' not in response:
			return({'error':'problemImmediateEvents'})


	# schedule any future events 
	for event in current_segment["followup_events"]:
		response = events.scheduleEvent(vizierUserId, vizierStudyId, event, fb,scheduler)	

		if 'success' not in response:
			return({'error':'problemFollowupEvents'})

	return({"vizierUserId":vizierUserId})


def updateUser(args, fb, scheduler, emailer):
	'''register completion for a segmentId, cancel outstanding events, process all immediate events for the next segment, schedule the followup events for the next segments, and update the state of the user to reflect their new segment'''

	vizierUserId, vizierSegmentId, payload = utils.extractOrComplain(args, ['vizierUserId', 'vizierStudyId', vizierSegmentId, 'payload'])	
    
	# confirm that the segment for this user is in a state where it can be updated (to handle errant API calls)
	user = fb.reference('users/'+vizierUserId).get()
	vizierStudyId = user['vizierStudyId']

	if user['segment'] != study[vizierSegmentId]:
		# Vizier thinks that the user is not in the state that is currently being registed as complete. This is likely an errant API call, and will be ignored
		return({'error':'inconsistentSegment'})

	# log that this was completed 
	fb.reference('completed/'+vizierUserId).update({
		'segment':segmentId,
		'time': utils.now('Etc/UTC'),
		'payload': payload # for logging, we lee[ the payload around]
	})

	# update user vars with received payload, without overwriting
	fb.reference('completed/'+vizierUserId+'/payload').update(payload)

	# removes any outstanding jobs in the scheduler from the completed segment
	events.cancelEvents(vizierUserId, vizierStudyId, vizierSegmentId
, scheduler)

	# process the next segments
	for next_segment_id in study[vizierSegmentId]['next_segments']:

		if next_segment_id == '$END$':
			# no next step to process if that was a final segment
			continue
		
		for event in study[next_segment_id]['immediate_events']:
			response = events.processEvent(vizierUserId, vizierStudyId, event, fb, emailer)

			if 'success' not in response:
				return({'error':'problemImmediateEvents'})

		for event in study[next_segment_id]['followup_events']:
			response = events.scheduleEvent(vizierUserId, vizierStudyId, event, scheduler, emailer)
			if 'success' not in response:
				return({'error':'problemFollowupEvents'})

		# update the state of the user in Firebase
		fb.reference('users/'+vizierUserId+'/segment').set(next_segment_id)

	return({'success':1})


def removeUser(args, fb, scheduler):
	'''Remove a user, both from scheduled events and from Firebase'''
	vizierUserId = utils.extractOrComplain(args, ['vizierUserId'])
	
	vizierUser = fb.reference('users/'+vizierUserId).get()
	if vizierUser is not None:
		# remove the user from Firebase
		fb.reference('users/'+vizierUserId).delete()
		# remove anything belonging to this user from the scheduler	
		events.cancelEvents(vizierUserId, None, None, scheduler)
	else:
		return({'error':'vizierUserIdNotFound'})

	return({'success':1})


def inviteUser(vizierStudyId, identifier, emailer):
	raise NotImplementedError		