# -*- coding: utf-8 -*-
from openerp import exceptions,models, fields, api, _
import pdb
import logging
from datetime import date,datetime,timedelta
from pytz import timezone
from dateutil import tz
import time

from zeep import Client

_logger = logging.getLogger(__name__)

transics_client = []
transics_list = []
# import logging.config

# logging.config.dictConfig({
#     'version': 1,
#     'formatters': {
#         'verbose': {
#             'format': '%(name)s: %(message)s'
#         }
#     },
#     'handlers': {
#         'console': {
#             'level': 'DEBUG',
#             'class': 'logging.StreamHandler',
#             'formatter': 'verbose',
#         },
#     },
#     'loggers': {
#         'zeep.transports': {
#             'level': 'DEBUG',
#             'propagate': True,
#             'handlers': ['console'],
#         },
#     }
# })




class transics(models.Model):
	_name="transics.transics"

	def _makeLogin(self):
		global transics_client
		if not transics_client:
			transics_client=Client(self.env['ir.config_parameter'].get_param('transics.transics_url',''))
		login={'DateTime':datetime.now(),
				'Version':1,
				'Language':'EN',
				'Dispatcher':self.env['ir.config_parameter'].get_param('transics.dispatcher',''),
				'Password':self.env['ir.config_parameter'].get_param('transics.password',''),
				'SystemNr':self.env['ir.config_parameter'].get_param('transics.systemnr',''),
				'Integrator':self.env['ir.config_parameter'].get_param('transics.integrator',''),
				}
		return login

#	def test_login(self, transics_account):
			

	def zGet_PositionFromStreetInfo(self,City=None,PostalCode=None,Street=None,Number=None,CountryCode='BEL'):
		request_data = {
					'Login':self._makeLogin(),
					'StreetInfo':{
					'CountryCode':CountryCode,
					},  
				}
		if City and len(City)>0:
			request_data['StreetInfo']['City']=City
		if PostalCode and len(PostalCode)>0:
			request_data['StreetInfo']['PostalCode']=PostalCode
		if Street and len(Street)>0:
			request_data['StreetInfo']['Street']=Street
		response=transics_client.service.Get_PositionFromStreetInfo(**request_data)
		return response



	def zInsert_Planning(self,planninginsert=None):
		request_data = {
			'Login':self._makeLogin(),
			'PlanningInsert':planninginsert
			}
		response=transics_client.service.Insert_Planning(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response

	def zCancel_Planning(self,planningitemselection=None):
		request_data = {
			'Login':self._makeLogin(),
			'PlanningItemSelection':planningitemselection
			}
		response=transics_client.service.Cancel_Planning(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response	




	@api.multi	
	def dispatcher_query(self,dummy=None):
		logging.info("Transics dispatcher query : %s " % self.env.user.name)
#		pdb.set_trace()
		self.env.user.company_id.transics_account_id.refresh_transics()

				
class transics_log(models.Model):
	_name="transics.log"
	_order="create_date DESC"
	MaximumModificationDate=fields.Datetime()
	errors=fields.Char()
	warnings=fields.Char()
	response=fields.Char()
	request_data=fields.Char()
	transics_account_id=fields.Many2one("transics.account")


class transics_account(models.Model):
	_name="transics.account"
	name=fields.Char()
	activity_ids=fields.One2many('transics.activity', 'transics_account_id')
	transics_url = fields.Char('Transics url', required=True )
	dispatcher = fields.Char( required=True, default="LUBON")
	password = fields.Char( required=True)
	systemnr = fields.Char( required=True)
	integrator = fields.Char( required=True, default="LUBON")
	language = fields.Char( required=True, default="NL")
	last_sync=fields.Datetime(help="Last ModificationDate returned by transics")
	oldest_missing=fields.Datetime(help="Oldest hist record without feedback")
	refresh_type=fields.Selection([('transics','Based on transics max ModificationDate'),('odoo','Based on odoo oldest incomplete record')])
	time_offset=fields.Integer(help="Time offset between Transics and Odoo")
	log_ids=fields.One2many('transics.log','transics_account_id')

	@api.multi
	def update_all_dest(self):
		#function to update all destinations
		load=self.env['transics.activity'].search([('name','=','Load'),('transics_account_id','=',self.env.user.company_id.transics_account_id.id)]).id
		unload=self.env['transics.activity'].search([('name','=','Unload'),('transics_account_id','=',self.env.user.company_id.transics_account_id.id)]).id
		#pdb.set_trace()
		for dest in self.env["hertsens.destination"].search([]):
			if dest.activity_id=="load":
				dest.transics_activity_id=load
			if dest.activity_id=="unload":
				dest.transics_activity_id=unload

	@api.multi
	def test_login(self):
		result=self.Get_ServerTime()
		raise exceptions.Warning(result)
		return True


	@api.multi
	def load_activities(self):
		result=self.Get_ActivityList()
		for activity in result['Activities']['ActivityVersionResult'][-1]['Activities']['ActivityInfo']:
			#pdb.set_trace()
			if not self.activity_ids.search_count([('transics_id','=',activity['ID']), ('transics_account_id','=',self.id)]):
				self.activity_ids.create({
					'transics_account_id':self.id,
					'transics_id':activity['ID'],
					'name':activity['Name'],
					'is_planning':activity['IsPlanning'],
					'activity_type':activity['Name'],
					'pathinfos':activity['PathInfos'],
					})
	def _makeLogin(self):
		global transics_list
		client=None

		if not transics_list:
			transics_list=[]
		for a in transics_list:
			if a['account_id']==self.id:
				client=a['client']
		if not client:
			client=Client(self.transics_url)
			transics_list.append(
				{'account_id':self.id,
				'client': client})

		login={'DateTime':datetime.now(),
				'Version':1,
				'Language':self.language,
				'Dispatcher':self.dispatcher,
				'Password':self.password,
				'SystemNr':self.systemnr,
				'Integrator':self.integrator,
				}

		result={'login': login, 'client': client}
		return result

	def Get_ServerTime(self, ):
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
			}
		response=transics['client'].service.Get_ServerTime(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response	

	def Get_ActivityList(self, ActivitySelection={}):	
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
			'ActivitySelection':ActivitySelection,
			}


		response=transics['client'].service.Get_ActivityList(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response	




	def Get_Scanned_Documents(self, ScannedDocumentsSelection={}):	
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
			'ScannedDocumentsSelection':ScannedDocumentsSelection,
			}


		response=transics['client'].service.Get_Scanned_Document(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response	


	def Get_Scanned_Document(self, ScannedDocumentSelection={'ScanID':123445, 'ConvertToPdf': True}):	
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
			'scannedDocumentSelection':ScannedDocumentSelection,
			}

		
		response=transics['client'].service.Get_Scanned_Document_V4(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response	


	def Insert_Planning(self,planninginsert=None):
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
			'PlanningInsert':planninginsert,
			}

		response=transics['client'].service.Insert_Planning(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response


	def Cancel_Planning(self,planningitemselection=None):
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
			'PlanningItemSelection':planningitemselection
			}
		response=transics['client'].service.Cancel_Planning(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response	

	def Get_PositionFromStreetInfo(self,City=None,PostalCode=None,Street=None,Number=None,CountryCode='BEL'):
		transics=self._makeLogin()
		request_data = {
			'Login':transics['login'],
					'StreetInfo':{
					'CountryCode':CountryCode,
					},  
				}
		if City and len(City)>0:
			request_data['StreetInfo']['City']=City
		if PostalCode and len(PostalCode)>0:
			request_data['StreetInfo']['PostalCode']=PostalCode
		if Street and len(Street)>0:
			request_data['StreetInfo']['Street']=Street
		response=transics['client'].service.Get_PositionFromStreetInfo(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response



	@api.multi	
	def refresh_transics(self,dummy=None):
		transics=self._makeLogin()
		#pdb.set_trace()
#		startdate=fields.Datetime.from_string(self.env['ir.config_parameter'].get_param('transics.MaximumModificationDate'))
		if self.refresh_type == 'odoo':
			startdate=fields.Datetime.from_string(self.oldest_missing)
		else:
			startdate=fields.Datetime.from_string(self.last_sync)
		if not startdate:
			startdate=datetime.now()
		enddate=datetime.now()
		offset = timedelta(hours=self.time_offset)
		startdate +=offset
		#pdb.set_trace()
		enddate +=offset

		request_data = {
			'Login':transics['login'],
			'PlanningModificationsSelection':{
				'PlanningSelectionType':'ALL',
				'DateTimeRange':{'StartDate': startdate, 'EndDate': enddate}
			}
			}
		#logger.info(request_data) 

		response=transics['client'].service.Get_Planning_Modifications_V8(**request_data)
		self.env['transics.log'].create({'response':str(response),
										'request_data':str(request_data),
										'transics_account_id': self.id,
										})
		if response['Errors']:
			_logger.info("Error Get_Planning_Modifications_V8")
		else:
			self.last_sync=response['MaximumModificationDate'] - timedelta(hours=self.time_offset, minutes=1) #- timedelta(minutes=1) #
		
		if 'Places' in response and response['Places']:
			for place in response['Places']['PlaceItemResult_V5']:
				hist=self.env['hertsens.destination.hist'].search([('place_id', "=",place['PlaceId'])])
				if not hist:
					hist=self.env['hertsens.destination.hist'].create({
						'place_id': place['PlaceId'],
						})
				hist.cancelstatus=place['CancelStatus']	
				hist.transferstatus=place['TransferStatus']	
				hist.status=place['Status']	
				hist.lastupdate=place['ModificationDate']-offset
				hist.raw=place
				if place['Driver']:
					driver = self.env['hr.employee'].search([('transics_id', "=",place['Driver']['ID'])])
					if driver:
						hist.employee_id=driver.id
				hist.hertsens_destination_id.checkstatus()		

		if 'ExtraInfos' in response and response['ExtraInfos']:
			for info in response['ExtraInfos']['ExtraInfo_V3']:
				p=info['Place']['CustomerID']
				hist=self.env['hertsens.destination.hist'].search([('place_id', "=",info['Place']['CustomerID'])])
				if hist and info['TypeCode'] == 'CMR':
					hist.cmr=info['Info']
				if hist and info['TypeCode'] == 'EUU':
					hist.pallet_unload=info['Info']
				if hist and info['TypeCode'] == 'EUL':
					hist.pallet_load=info['Info']
				if hist and info['TypeCode'] == 'NOK':
					hist.status ='ABORTED'
					hist.hertsens_destination_id.checkstatus()
					#pdb.set_trace()

		if 'Consultation' in response and response['Consultation']:
			for consult in response['Consultation']['Consultation_V4']:
				#pdb.set_trace()
				hist=self.env['hertsens.destination.hist'].search([('place_id', "=",consult['Place']['PlaceID'])])
				if hist:
					hist.km=consult['Km']
					if consult['ArrivalDate']:
						hist.arrivaldate=consult['ArrivalDate'] - offset
					if 	consult['LeavingDate']: 
						hist.leavingdate=consult['LeavingDate'] - offset
					if consult['Position']:
						hist.longitude=consult['Position']['Longitude']
						hist.latitude=consult['Position']['Latitude']
		if 'ScannedDocuments' in response and response['ScannedDocuments']:
			for doc in response['ScannedDocuments']['Document_V5']:
				scanned_doc=self.Get_Scanned_Document(ScannedDocumentSelection={'ScanID':doc['ScanID'], 'ConvertToPdf': True})
				for att in scanned_doc['Documents']['DocumentResult_V4']:
					ride_id=self.env['hertsens.destination.hist'].search([('place_id', "=",att['Place']['PlaceID'])]).ride_id
					if ride_id:
						b=self.env['ir.attachment'].create({
							'res_id':ride_id.id,
							'res_model':'hertsens.rit',
							'name':att['FileName'],
							'datas': att['Document'],
							})
					else:
						_logger.warning('Rit bij scan %d niet gevonden' % doc['ScanID'])

		self.oldest_missing=None
		missing=self.env['hertsens.destination.hist'].search([('lastupdate','=',False)]).sorted(key=lambda l: l.lastupdate)
		#pdb.set_trace()
		if missing:
			self.oldest_missing=missing[0].create_date


class transics_activities(models.Model):
	_name="transics.activity"
	_order="is_planning DESC, sequence, name"
	transics_account_id=fields.Many2one('transics.account', required=True)
	dispatch_enabled=fields.Boolean(help="Enabled for dispatch operations?")
	transics_id=fields.Integer()
	name=fields.Char()
	sequence=fields.Integer()
	is_planning=fields.Boolean()
	activity_type=fields.Char()
	pathinfos=fields.Char()
	oldname=fields.Char()



class base_config_settings(models.TransientModel):
	_name = 'transics.config.settings'
	_inherit = 'res.config.settings'
	_order = 'create_date DESC'

	def _get_transics_url(self):
		return self.env['ir.config_parameter'].get_param('transics.transics_url', '')
	def _get_transics_dispatcher(self):
		return self.env['ir.config_parameter'].get_param('transics.dispatcher', '')

	def _get_transics_password(self):
		return self.env['ir.config_parameter'].get_param('transics.password', '')

	def _get_transics_systemnr(self):
		return self.env['ir.config_parameter'].get_param('transics.systemnr', '')

	def _get_transics_integrator(self):
		return self.env['ir.config_parameter'].get_param('transics.integrator', '')
	def _get_transics_act_load_id(self):
		return self.env['ir.config_parameter'].get_param('transics.act_load_id', '')
	def _get_transics_act_unload_id(self):
		return self.env['ir.config_parameter'].get_param('transics.act_unload_id', '')

	transics_url = fields.Char('Transics url', required=True, default=_get_transics_url)
	dispatcher = fields.Char( required=True,default=_get_transics_dispatcher)
	password = fields.Char( required=True, default=_get_transics_password)
	systemnr = fields.Char( required=True, default=_get_transics_systemnr)
	integrator = fields.Char( required=True, default=_get_transics_integrator)
	act_load_id = fields.Char( required=True, default=_get_transics_act_load_id)
	act_unload_id = fields.Char( required=True, default=_get_transics_act_unload_id)

	@api.model
	def set_transics_url(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.transics_url', config.transics_url)
	
	@api.model
	def set_password(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.password', config.password)

	@api.model
	def set_dispatcher(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.dispatcher', config.dispatcher)

	@api.model
	def set_systemnr(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.systemnr', config.systemnr)

	@api.model
	def set_integrator(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.integrator', config.integrator)

	@api.model
	def set_act_load_id(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.act_load_id', config.act_load_id)

	@api.model
	def set_act_unload_id(self, ids):
		config = self.browse(ids[0])
		icp = self.env['ir.config_parameter']
		icp.set_param('transics.act_unload_id', config.act_unload_id)
