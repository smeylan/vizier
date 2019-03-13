import os, pdb, urllib, json, logging, vizier
logging.captureWarnings(True)
from nose.tools import *
from vizier import app
app.testing = True
test_app = app.test_client()

def check_status_code(rv):
	if rv.status_code != 200:
		raise ValueError('Status code is '+ str(rv.status_code))

def check_content_type(headers, expectedOutput):
	print('Expected output is of type:')
	print(type(expectedOutput))
	if isinstance(expectedOutput, dict) or isinstance(expectedOutput, list) or isinstance(expectedOutput, tuple):
		if headers['Content-Type'] not in (u'application/json'):
			raise ValueError('Return document is "'+ headers['Content-Type'] +'", not "application/json"')
	else:	
		if headers['Content-Type'] not in (u'text/html; charset=utf-8', u'text/html'):
			raise ValueError('Return document is "'+ headers['Content-Type'] +'", not "text/html"')

def check_return_data(returnData, expectedOutput):
	'''if a dict, check that the returned json is the same. If a list, check that the dictionary has those keys. If a string, check that the return value is the same string'''
	print('Return Data:')	
	print(returnData)
	
	if isinstance(expectedOutput, dict):
		robject = json.loads(returnData)
		#if expectedOutput is a dictionary, compare all fields and values			
		for key in expectedOutput.keys():
			if robject[key] != expectedOutput[key]:
				raise ValueError('Unexpected return value. Expected "'+expectedOutput[key]+'"" for key "' + key + '", received "'+ returnData[key]+'"')
	elif isinstance(expectedOutput, list):
		robject = json.loads(returnData)
		#if expectedOutput is a list, compare that the first item has all the same fields
		for item in range(len(robject)):
			for key in expectedOutput[item].keys():
				if key not in robject[item].keys():
					raise ValueError('Unexpected return value. Key missing: "'+key+'"')
	elif isinstance(expectedOutput, tuple):		
		robject = json.loads(returnData)
		#if expectedOutput is a tuple, check that the returnObject has all keys
		for key in expectedOutput:
			if key not in robject.keys():
				raise ValueError('Unexpected return value. Key missing: "'+key+'"')
	else:	
		if eq_(returnData, expectedOutput) is not None:			
			raise ValueError('Unexpected return value. Expected: '+expectedOutput+'. Received: '+returnData)


class FlaskRouteTester():
  def __init__(self, url, input, output):  
    self.url = url
    self.input = input 
    self.output	= output
    self.headers = {
      'Content-Type': 'application/json',
    }

  def test(self, method='GET'):
		
    url_string = urllib.urlencode(self.input)
    print('-----Testing '+self.url+' with input ['+url_string+'] ...')
    url_string = urllib.urlencode(self.input)

    print('url:')	
    print(self.url)	

    if method == 'GET':
      rv = test_app.get(self.url+'?'+url_string)       
    elif method == "POST":
      rv = test_app.post(self.url, data=self.input, headers=self.headers) 
    else:
      raise ValueError('Method not recognized')  
		
		#check the status code
    check_status_code(rv)

		#check the headers
    check_content_type(rv.headers, self.output)
    if (self.output is not None):
      check_return_data(rv.data, self.output)
      
    print('\t-Route passed!')
	

def test_routes():

  print('Testing routes...')

  # check / 
  t = FlaskRouteTester('/',{},'Flask is running!')
  t.test()		

  # check addUser
  t = FlaskRouteTester('/addUser',{"vizierStudyId":"ContinuousCDI","payload":{"identifier":"meylan.stephan@gmail.com"}},{"success":1})
  t.test()    

  
  #t = FlaskRouteTester('/addUser',,{"success":1})
  #t.test()    

  print('All tests passed!')

test_routes()

