from ckanapi import LocalCKAN

from ckan.tests.helpers import reset_db
from ckan.lib.search import clear_all


class RecombinantTestBase(object):
    @classmethod
    def setup_method(self, method):
        """Method is called at class level before EACH test methods of the class are called.
        Setup any state specific to the execution of the given class methods.
        """
        reset_db()
        clear_all()

        lc = LocalCKAN()

        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': 'text'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF (value = '') IS NOT FALSE THEN
                RETURN ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': '_text'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF value IS NULL OR value = '{}' THEN
                return ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': 'date'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF value IS NULL THEN
                RETURN ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': 'numeric'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF value IS NULL THEN
                RETURN ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': 'int4'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF value IS NULL THEN
                RETURN ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': 'money'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF value IS NULL THEN
                RETURN ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
        lc.action.datastore_function_create(
            name='required_error',
            or_replace=True,
            arguments=[
                {'argname': 'value', 'argtype': 'boolean'},
                {'argname': 'field_name', 'argtype': 'text'}],
            rettype='_text',
            definition='''
        BEGIN
            IF value IS NULL THEN
                RETURN ARRAY[[field_name,
                'This field must not be empty']];
            END IF;
            RETURN NULL;
        END;
            ''')
