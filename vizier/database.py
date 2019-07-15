from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.automap import automap_base
import config

Base = automap_base() # any table needs a primary key for automapping
engine = create_engine(config.POSTGRES_CONNECTION_STRING, convert_unicode=True)
Base.prepare(engine, reflect=True)

giftcodes = Base.classes.giftcodes

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def sql_to_json(results):
	json_results = []
	for item in results:
		if hasattr(item, '__table__'):
			#item is a row from SQL alchemy
			row = item
			d = {}
			for column in row.__table__.columns:
				d[column.name] = getattr(row, column.name)
			json_results.append(d)
		else:
			#item is not a row
			json_results.append(item)
	return(Response(json.dumps(json_results, default=alchemyencoder), mimetype="application/json"))
