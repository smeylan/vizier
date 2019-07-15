# import error catching in sentry
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://26e4365f93594a49bce6381099e17500@sentry.io/1395668",
    integrations=[FlaskIntegration()]
)

# general libraries
import os
import sys
import urllib
import json
import pytz
import pandas as pd

# app modules
import user
import events
import email_google
import ouvrecompensate


# for flask, rate limiter, CORS
import config
from flask import Flask, request, jsonify, send_from_directory, Response, render_template, make_response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# for logging
import logging
from logging.handlers import RotatingFileHandler
from logging import getLogger

# Firebase

import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# Postgres

import sqlalchemy
from database import db_session

# initialize Flask app
app = Flask(__name__)
app.debug = config.FLASK_DEBUG
app.config['JSON_AS_ASCII'] = False # force UTF-8 encoding
cors = CORS(app)
# if config.PRODUCTION == "1":
#     sentry = Sentry(app)

# scheduling
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ProcessPoolExecutor

# initialize logging for flask
if not os.path.exists('logs'):
    os.makedirs('logs')
flask_handler = RotatingFileHandler('logs/vizier_flask.log', maxBytes =10000, backupCount=2)
app.logger.addHandler(flask_handler)
app.logger.setLevel(logging.INFO)

# initialize logging for apschedulder
apscheduler_handler = RotatingFileHandler('logs/vizier_apscheduler.log', maxBytes=10000, backupCount=2)
apscheduler_logger = logging.getLogger('apscheduler.executors.default')
apscheduler_logger.addHandler(apscheduler_handler)
apscheduler_logger.setLevel(logging.INFO)
apscheduler_stream_handler = logging.StreamHandler() #log apscheduler to stdout
apscheduler_logger.addHandler(apscheduler_stream_handler)


# Load Firebase connection
if os.path.exists(config.FIREBASE_AUTH_TOKEN_PATH):
    # on CircleCI, this should have been written to in the preflight script
    print('Using local JSON as Firebase credential')
    cred = credentials.Certificate(config.FIREBASE_AUTH_TOKEN_PATH)
else:    
    print('Generating Firebase credential from environment variables')
    cred = credentials.Certificate({
      "type": "service_account",
      "project_id": "vizier-staging",
      "private_key_id": "b7580f898c84c03712d0645bf2a91ccb158444d9",
      "private_key": config.FIREBASE_PRIVATE_KEY,
      "client_email": config.FIREBASE_EMAIL,
      "client_id": "108419503168918295488",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"+urllib.quote(config.FIREBASE_EMAIL)
    })
    
    

firebase_admin.initialize_app(cred, {
    'databaseURL': config.FIREBASE_URL
})
fb = db

emailer = email_google.Gmail(config.EMAIL_RELAY_ADDRESS, config.EMAIL_RELAY_PW)

# initialize a scheduler for background tasks from apscheduler
jobstores = {
    'default': SQLAlchemyJobStore(
    url = config.POSTGRES_CONNECTION_STRING,
    tablename =  'apscheduler_jobs_dev' if config.PRODUCTION == "0" else 'apscheduler_jobs')
}
executors = {
    'default': {'type': 'threadpool', 'max_workers': 1},
    'processpool': ProcessPoolExecutor(max_workers=1)
}
scheduler = BackgroundScheduler()
scheduler.configure(jobstores=jobstores, executors=executors, timezone="UTC")
scheduler.start()

# initialize the job scheduler 
limiter = Limiter(
    app,
    key_func=get_remote_address,
    global_limits=["2000 per day", "200 per hour"]
)


# ROUTES - ACTIVE
@app.route('/', )
def index():
    return 'Flask is running!'

@limiter.limit("100 per hour")
@app.route('/addUser', methods=['POST','GET'])
def addUser(): # vizierStudyId, payload
    print('Add user called!')
    if request.method == 'POST':   
        args = request.get_json()
    elif request.method == 'GET':   
        args = request.args.to_dict()
    response = user.addUser(args, fb, emailer, scheduler)
    return(jsonify(response))  


@limiter.limit("100 per hour")
@app.route('/registerSegmentCompletion', methods=['POST','GET']) 
def registerSegmentCompletion(): # vizierUserId, vizierSegmentId, payload
    if request.method == 'POST':   
        args = request.get_json()
    elif request.method == 'GET':   
        args = request.args.to_dict()
    response = user.registerSegmentCompletion(args, fb, scheduler, emailer)
    return(jsonify(response))  

@limiter.limit("10 per hour")
@app.route('/removeUser', methods=['POST','GET']) 
def removeUser(): # vizierUserId
    if request.method == 'POST':   
        args = request.get_json()
    elif request.method == 'GET':   
        args = request.args.to_dict()
    response = user.removeUser(args, fb, scheduler)
    return(jsonify(response))  

@limiter.limit("10 per hour")
@app.route('/inviteUser', methods=['POST','GET']) 
def inviteUser(): #  vizierStudyId, identifier
    if request.method == 'POST':   
        args = request.get_json()
    elif request.method == 'GET':   
        args = request.args.to_dict()
    response = user.inviteUser(args, fb, scheduler, emailer)
    return(jsonify(response))  

@limiter.limit("100 per hour")
@app.route('/scheduledEventHandler', methods=['POST','GET']) 
def scheduledEventHandler(): # arbitrary payload
    if request.method == 'POST':   
        args = request.get_json()
    elif request.method == 'GET':   
        args = request.args.to_dict()
    response = events.scheduledEventHandler(args, fb, emailer)
    return(jsonify(response))  
   
# compensation system
@limiter.limit("10 per hour")
@app.route('/compensate', methods=['POST','GET']) 
def compensate(): # payload depends on the method; all have method, authToken, studyId
    if request.method == 'POST':   
        args = request.get_json()
    elif request.method == 'GET':   
        args = request.args.to_dict()
    response = compensate.compensate(args, fb, emailer, db_session)
    return(jsonify(response))  

@limiter.limit("10 per hour")
@app.route('/uploadGiftCodes', methods=['POST','GET']) 
def uploadGiftCodes():
    if request.method == "POST":
        file = request.files["file"]
        studyId = request.form["studyId"]
        authToken = request.form["authToken"]        
        
        if studyId not in fb.reference('studies/').get():
            res = make_response(jsonify({"message": "studyId not recognized"}), 200)
            return res

        if fb.reference('studies/'+studyId+'/authToken').get() != authToken:
            res = make_response(jsonify({"message": "Invalid authToken"}), 200)
            return res

        print("File uploaded")
        print(file)

        csv_contents = pd.read_csv(file)

        # establish a connection to the datbase
        existingGiftCodes = pd.read_sql_query('select * from giftcodes', con=database.engine)

        # get the set of compensation codes in there already
        to_add = csv_contents.loc[~csv_contents.giftCode.isin(existingGiftCodes.giftCode)]

        # compute the number of updated items
        num_new_records = to_add.shape[0] 
        print('Adding '+str(num_new_records)+ ' new gift codes...')

        if to_add.shape[0] > 0:
            # add those items
            to_add.to_sql('giftcodes', database.engine, index=False, if_exists="append")
        

        res = make_response(jsonify({"message": "File uploaded; "+str(num_new_records) + ' gift codes added'}), 200)
        return res
    return render_template("upload_giftcodes.html")

