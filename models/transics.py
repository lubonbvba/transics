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
	def Get_PositionFromStreetInfo(self,City=None,PostalCode=None,Street=None,Number=None,CountryCode='BEL'):
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



	def Insert_Planning(self,planninginsert=None):
		request_data = {
			'Login':self._makeLogin(),
			'PlanningInsert':planninginsert
			}
		response=transics_client.service.Insert_Planning(**request_data)
		if response['Errors']:
			raise exceptions.Warning(response)
		return response

	def Cancel_Planning(self,planningitemselection=None):
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
		#pdb.set_trace()
		startdate=fields.Datetime.from_string(self.env['ir.config_parameter'].get_param('transics.MaximumModificationDate'))
		if not startdate:
			startdate=datetime.now() - timedelta(hours=1)
		enddate=datetime.now()
		offset = timedelta(hours=1)
#		startdate +=offset
		#pdb.set_trace()
		enddate +=offset
		request_data = {
			'Login':self._makeLogin(),
			'PlanningModificationsSelection':{
				'PlanningSelectionType':'ALL',
				'DateTimeRange':{'StartDate': startdate, 'EndDate': enddate}
			}
			}
		#logger.info(request_data) 
		#pdb.set_trace()
		response=transics_client.service.Get_Planning_Modifications_V8(**request_data)
		#pdb.set_trace()
		self.env['transics.log'].create({'response':str(response),
										'request_data':str(request_data)
										})
		if response['Errors']:
			_logger.info("Error Get_Planning_Modifications_V8")
		else:
			self.env['ir.config_parameter'].sudo().set_param('transics.MaximumModificationDate', response['MaximumModificationDate'] - timedelta(minutes=1))
		
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
					driver = self.env['res.users'].search([('transics_id', "=",place['Driver']['ID'])])
					if driver:
						hist.driver_id=driver.id
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
				#pdb.set_trace()

		
class transics_log(models.Model):
	_name="transics.log"

	MaximumModificationDate=fields.Datetime()
	errors=fields.Char()
	warnings=fields.Char()
	response=fields.Char()
	request_data=fields.Char()


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
