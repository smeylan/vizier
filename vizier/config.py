import os

project_name = 'VIZIER'

env_vars = [
	'BASE_URL',
	'FLASK_DEBUG',
	'FIREBASE_AUTH_TOKEN_PATH',	
	'FIREBASE_URL',
	'FIREBASE_PRIVATE_KEY',
	'FIREBASE_EMAIL',
	'PRODUCTION',
	'POSTGRES_CONNECTION_STRING',	
	'EMAIL_RELAY_ADDRESS',
	'EMAIL_RELAY_PW'
]

for env_var in env_vars:	
	vars()[env_var] = os.environ[project_name+'_'+env_var]
