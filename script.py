from pymisp import PyMISP
from pymisp import ExpandedPyMISP
import config
from collections import defaultdict
import datetime
from RequestManager import RequestManager
from RequestObject import RequestObject
from constants import *
import sys
from functools import reduce
from  nested_lookup import nested_lookup


def _get_events():
    misp = ExpandedPyMISP(config.misp_domain, config.misp_key, config.misp_verifycert)
    if len(config.misp_event_filters) == 0:
        return [event['Event'] for event in misp.search(controller='events', return_format='json')]
    events_for_each_filter = [
        [event['Event'] for event in misp.search(controller='events', return_format='json', **config.misp_event_filters)]
    ]
    event_ids_for_each_filter = [set(event['id'] for event in events) for events in events_for_each_filter]
    event_ids_intersection = reduce((lambda x, y: x & y), event_ids_for_each_filter)
    return [event for event in events_for_each_filter[0] if event['id'] in event_ids_intersection]


def _graph_post_request_body_generator(parsed_events):
    for event in parsed_events:
        print(event)
        request_body_metadata = {
            **{field: event[field] for field in REQUIRED_GRAPH_METADATA},
            **{field: event[field] for field in OPTIONAL_GRAPH_METADATA if field in event},
            'action': config.action,
            'passiveOnly': config.passiveOnly,
            'threatType': 'watchlist',
            'targetProduct': config.targetProduct,
        }
        for request_object in event['request_objects']:
            request_body = {
                **request_body_metadata.copy(),
                **request_object.__dict__,
                'tags': request_body_metadata.copy()['tags'] + request_object.__dict__['tags']
            }
            yield request_body


def _handle_timestamp(parsed_event):
    parsed_event['lastReportedDateTime'] = str(
        datetime.datetime.fromtimestamp(int(parsed_event['lastReportedDateTime'])))


def _handle_diamond_model(parsed_event):
    for tag in parsed_event['tags']:
        if 'diamond-model:' in tag:
            parsed_event['diamondModel'] = tag.split(':')[1]


def _handle_tlp_level(parsed_event):
    for tag in parsed_event['tags']:
        if 'tlp:' in tag:
            parsed_event['tlpLevel'] = tag.split(':')[1]
    if 'tlpLevel' not in parsed_event:
        parsed_event['tlpLevel'] = 'red'


def main():
    if '-r' in sys.argv:
        RequestManager.read_tiindicators()
        sys.exit()
    config.verbose_log = ('-v' in sys.argv)
    print('fetching & parsing data from misp...')
    events = _get_events()
    parsed_events = list()
    for event in events:
        
        parsed_event = defaultdict(list)
        for key, mapping in EVENT_MAPPING.items():
            parsed_event[mapping] = event.get(key, "")
        parsed_event['tags'] = [tag['name'].strip() for tag in event.get("Tag", [])]
        _handle_diamond_model(parsed_event)
        _handle_tlp_level(parsed_event)
        _handle_timestamp(parsed_event)
        
        all_attributes = nested_lookup(key = 'Attribute', document = event, wild = False)
        atrib_list = list()
 
        print("lengde: ",  len(all_attributes))    
        for attr in all_attributes:
            for  a in attr:
                print("a :" , a)
                if a['type'] == 'threat-actor':
                    parsed_event['activityGroupNames'].append(a['value'])
                if a['type'] == 'comment':
                    parsed_event['description'] += a['value']
                if a['type'] in MISP_ACTIONABLE_TYPES:
                    parsed_event['request_objects'].append(RequestObject(a))

        parsed_events.append(parsed_event)
    del events

    total_indicators = sum([len(v['request_objects']) for v in parsed_events])
    with RequestManager(total_indicators) as request_manager:
        for request_body in _graph_post_request_body_generator(parsed_events):
            print(f"request body: {request_body}")
            request_manager.handle_indicator(request_body)


if __name__ == '__main__':
    main()