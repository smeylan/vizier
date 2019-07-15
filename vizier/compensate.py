def compensate(args, fb, emailer, db_session):
	'''wrapper for all methods, so that the `verb` is specified in the posted data file'''

	# first, authenticate:
	method_name, authToken, studyId = utils.extractOrComplain(args, ['method', 'authToken', 'studyId'])		
	
	if not evalAuthToken(authToken, studyId, fb):
		return({'error':'authorization failed'})
		
	rv = method_list[method_name](args, fb, emailer, db_session)
	return(rv)

def evalAuthToken(authToken, studyId, fb):
	return(authToken == fb.reference('studies/'+studyId+'/authToken').get())


def addGiftCodes(args, fb, emailer, db_session):
	'''upload a csv with a set of gift codes; specify how many new ones have been added'''
	#!!! need to be able to specify which study gets these gift codes
	
	raise NotImplementedError	


def warnResearchers(num_remaining, studyId, fb, emailer):
	recipients = fb.reference('studies/'+studyId+'/researcherEmails').get()
	
	if num_remaining == 0:
		warningType = "none"
	else:
		warningType = "few"

	warnings = {
		"few": {"subject": str(len(num_remaining)) + " gift codes are remaining for "+studyId , 
			"body": "EOM"},
		"none": {"subject": "No gift codes are remaining for "+studyId, "body":"EOM"},
	}

	for recipient in recipients:
		emailer.message(
			subject = warnings[warningType]['subject'],
			body = warnings[warningType]['body'],
			recipient
		)		

def allocateGiftCode(args, fb, emailer, db_session):
	'''reserve a gift code for a give (user, study, segment) tuple'''
	this_userId, this_studyId, this_segmentId, force = utils.extractOrComplain(args, ['userId', 'studyId', 
		'segmentId','force'])	
	
	# check if this user has already had a code allocated or cashed in
	if not force:
		
		already_allocated  = compensationRecord.query.filter_by(_and(
			userId = this_userId,
			studyId = this_studyId,
			segmentId =this_segmentId,
			_or(status = "allocated", status='cashed_in')
		))

		if len(already_allocated) > 0: #!!! confirm that we can check the length of a result object
			return({'error':'userId already compensated'})

	# finding a gift code that hasn't been allocated yet
	comp_code = compensationRecord.query('compensationCode').filter_by(status = "unallocated")

	if len(comp_code) == 0:
		warnResearchers(len(comp_code), studyId, fb, emailer)
		return({'error':'no unallocated compensation codes are left'})
	
	elif len(comp_code) <= 5:
		warnResearchers(len(comp_code), studyId, fb, emailer)	

	# update the allocation
	result = compensationRecord.update().where(compensationRecord.c.compensationCode == comp_code).
        values(userId=this_userId, segmentId = this_segmentId, studyId=this_studyId,  status='allocated')

    if result.rowcount == 0:
    	return({'error':'No record with this compensation code for allocation'})

    return({'success':1})


def deallocateGiftCode(args, fb, emailer, db_session):
	'''cancel the reservation for a gift code'''
	giftCode, force = utils.extractOrComplain(args, ['giftCode', 'force'])
	
	# remove the gift code
	result = compensationRecord.update().where(compensationRecord.c.compensationCode == gift_code).
        values(userId='', studyId ='', segmentId = '', status='unallocated')

    if result.rowcount == 0:
    	return({'error':'No record with this compensation code for deallocation'})

    return({'success':1})


def getCodeStatus(args, fb, emailer, db_session):
	'''What is the status of this gift code?'''
	this_giftCode = utils.extractOrComplain(args, ['giftCode'])	
	records = compensationRecord.query.filter_by(giftCode=this_giftCode)
	if records is None:
		return({'error',"giftCode not found"})
	else:
		return(database.sql_to_json(records))

def getUserStatus(args, fb, emailer, db_session):
	'''What is the status of this userId?'''
	this_userId = utils.extractOrComplain(args, ['userId'])
	records = compensationRecord.query.filter_by(userId=this_userId)
	if records is None:
		return({'error',"userId not found"})
	else:
		return(database.sql_to_json(records))

def getSystemStatus(args, fb, emailer, db_session):
	'''How many unallocated, allocated, and cashed in gift codes are there?'''
	userId = utils.extractOrComplain(args, ['userId'])
	
	num_unallocated= len(compensationRecord.query.filter_by(status="unallocated"))
	num_allocated = len(compensationRecord.query.filter_by(status="allocated"))
	num_cashed_in = len(compensationRecord.query.filter_by(status="cashed_in"))
	
	return({'num_unallocated':num_unallocated,
			'num_allocated':num_allocated,
			'num_cashed_in':num_cashed_in})

method_list = {
    'addGiftCodes': addGiftCodes,
    'allocateGiftCode': allocateGiftCode,
    'deallocateGiftCode':deallocateGiftCode,
    'getCodeStatus':getCodeStatus,
    'getUserStatus': getUserStatus,
    'getSystemStatus':getSystemStatus
}