import ckanapi

from ckanext.recombinant.tables import get_dataset_type

def recombinant_create(context, data_dict):
    '''
    Create a dataset with datastore table(s) for an organization and
    recombinant dataset type.

    :param dataset_type: recombinant dataset type
    :param owner_org: organization name or id
    '''
    dataset_type = get_or_bust(data_dict, 'dataset_type')
    owner_org = get_or_bust(data_dict, 'owner_org')

    lc = ckanapi.LocalCKAN(username=context['user'])
    lc.action    
