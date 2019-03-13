import pytz
from datetime import datetime as dt

def extractOrComplain(args, keys):  
  return_values = [] 
  for key in keys:
    if key in args:
      return_values.append(args[key])
    else:
      print('Error for key:'+key)	
      return({'error':key+'NotSpecified'})  
  if len(return_values) > 1:  
    return(return_values)     
  else:
    return(return_values[0]) #in the single case, we don't want to return a singleton list


def now(tz_string,returnString=True):
  # get current time in tz
  tz = pytz.timezone(tz_string)
  t = dt.now(tz)  
  if returnString:
    return(t.strftime("%Y-%m-%d %H:%M:%S %z"))
  else:
    return(t)