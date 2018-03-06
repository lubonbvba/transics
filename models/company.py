# -*- coding: utf-8 -*-
from openerp import exceptions,models, fields, api, _
import pdb
import logging



class res_company(models.Model):
	_inherit="res.company"
	transics_account_id=fields.Many2one('transics.account')