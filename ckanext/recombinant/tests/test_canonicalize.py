# -*- coding: UTF-8 -*-
import pytest

from datetime import datetime, date

from ckanext.recombinant.datatypes import canonicalize, BadExcelData

def test_year():
    dt = 'year'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_month():
    dt = 'month'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_int():
    dt = 'int'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_bigint():
    dt = 'bigint'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_date():
    dt = 'date'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42.0'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42.0'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_timestamp():
    dt = 'timestamp'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42.0'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42.0'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_money():
    dt = 'money'
    assert canonicalize(2019, dt, False) == '2019.00'
    assert canonicalize(42.0, dt, False) == '42.00'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(42.25000001, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0.00'
    assert canonicalize('2019', dt, False) == '2019.00'
    assert canonicalize('42.0', dt, False) == '42.00'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('42.25000001', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0.00'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '1000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_text():
    dt = 'text'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42.0'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42.0'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == ''
    assert canonicalize('', dt, False) == ''
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_boolean():
    dt = 'boolean'
    assert canonicalize(2019, dt, False) == '2019'
    assert canonicalize(42.0, dt, False) == '42.0'
    assert canonicalize(42.25, dt, False) == '42.25'
    assert canonicalize(0, dt, False) == '0'
    assert canonicalize('2019', dt, False) == '2019'
    assert canonicalize('42.0', dt, False) == '42.0'
    assert canonicalize('42.25', dt, False) == '42.25'
    assert canonicalize('0', dt, False) == '0'
    assert canonicalize(None, dt, False) == None
    assert canonicalize('', dt, False) == None
    assert canonicalize('', dt, True) == ''
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == '2020-11-15'
    assert canonicalize(datetime(2020, 11, 15), dt, False) == '2020-11-15 00:00:00'
    assert canonicalize('$1,000.50', dt, False) == '$1,000.50'
    assert canonicalize('=TRUE()', dt, False) == 'TRUE'
    assert canonicalize('=FALSE()', dt, False) == 'FALSE'
    assert canonicalize('AB,CD,E', dt, False) == 'AB,CD,E'

def test_text_array():
    dt = '_text'
    assert canonicalize(2019, dt, False) == ['2019']
    assert canonicalize(42.0, dt, False) == ['42.0']
    assert canonicalize(42.25, dt, False) == ['42.25']
    assert canonicalize(0, dt, False) == ['0']
    assert canonicalize('2019', dt, False) == ['2019']
    assert canonicalize('42.0', dt, False) == ['42.0']
    assert canonicalize('42.25', dt, False) == ['42.25']
    assert canonicalize('0', dt, False) == ['0']
    assert canonicalize(None, dt, False) == []
    assert canonicalize('', dt, False) == []
    assert canonicalize('', dt, True) == []
    with pytest.raises(BadExcelData):
        canonicalize('=1+1', dt, False)
    assert canonicalize(date(2020, 11, 15), dt, False) == ['2020-11-15']
    assert canonicalize(datetime(2020, 11, 15), dt, False) == ['2020-11-15 00:00:00']
    assert canonicalize('$1,000.50', dt, False) == ['$1', '000.50']
    assert canonicalize('=TRUE()', dt, False) == ['TRUE']
    assert canonicalize('=FALSE()', dt, False) == ['FALSE']
    assert canonicalize('AB,CD,E', dt, False) == ['AB', 'CD', 'E']

def test_primary_key():
    dt = 'text'
    assert canonicalize('OGP-324', dt, True) == 'OGP-324'
    assert canonicalize('\t OGP-324\n', dt, True) == 'OGP-324'
    assert canonicalize('OGP-\r\n\r\n324', dt, True) == 'OGP-324'
    assert canonicalize('OGP- 324', dt, True) == 'OGP- 324'

def test_choice_field():
    assert canonicalize('C1 ', 'text', False, False) == 'C1 '
    assert canonicalize('C1 ', 'text', False, True) == 'C1'
    assert canonicalize(' C1: Value', 'text', False, False) == ' C1: Value'
    assert canonicalize(' C1: Value', 'text', False, True) == 'C1: Value'
    assert canonicalize(' C1: Value', 'text', False, 'full') == 'C1'
