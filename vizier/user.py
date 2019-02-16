def addUser():
	raise NotImplementedError


def updateUser():
	# Log that update has been called (using the UTC time)
    
    # confirm that the segment for this user is in a state where it can be updated (to handle errant API calls)
    # update user state, noting last completed segment
    # removes anything in the scheduler from the completed state
    # processEvent in immediate_events
    # add all events in followup_events to the scheduler
	
	raise NotImplementedError	


def removeUser():
	raise NotImplementedError		