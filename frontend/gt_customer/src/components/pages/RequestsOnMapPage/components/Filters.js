import React, { useEffect, useState } from 'react';

import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';

import ButtonsContainer from '../../../ButtonsContainer/ButtonsContainer';
import CustomSelectWithStorage from '../../../CustomSelectWithStorage/CustomSelectWithStorage';
import CustomAutocomplete from '../../../CustomAutocomplete/CustomAutocomplete';

import { REQUESTS_ON_MAP_PREFIX } from '../../../../utils/constants';
import { storageService } from '../../../../utils';

import {
    fetchLocation,
    fetchRequestsOnMap,
    fetchRequestsOnMapAutocomplete,
    setSelectedMapRequestId,
    setSelectedMapRequestType,
} from '../../../../actions';

import moment from 'moment';

import styles from './Filters.module.scss';

const localStorageService = storageService(REQUESTS_ON_MAP_PREFIX);

const titlePrefix = (count) => {
    const r100 = count % 100;
    const r10 = count % 10;
    let name = 'заявок';
    if (r100 === 1 || (r100 > 20 && r10 === 1)) {
        name = 'заявка';
    } else if ([2, 3, 4].includes(r100) || (r100 > 20 && [2, 3, 4].includes(r10))) {
        name = 'заявки';
    }

    return count + ' ' + name + ' в';
};

const Filters = (props) => {
    const [locations, setLocations] = useState([]);
    const fetchLocations = async () => {
        const response = await props.fetchLocation();
        const locations = response.payload.data.results.map((item) => ({
            id: +item.id,
            text: item.text,
        }));
        setLocations(locations);
    };
    useEffect(() => {
        fetchLocations();
    }, []);

    const selectedRequestText = () => {
        const request = props.delivery_requests_autocomplete.find((item) => {
            return item.id === props.selected_request_id;
        });
        if (request) {
            return request.text;
        }
        if (props.selected_request_id !== -1) {
            return props.selected_request_id;
        }
        return '';
    };

    const fetchRequestsOnMapAutocomplete = (text) => {
        let params = { q: text };
        const map_location = localStorageService.get('map_location');
        if (map_location !== -1) {
            params.forward = JSON.stringify({
                location: map_location,
                request_type: props.selected_request_type,
            });
        }
        props.fetchRequestsOnMapAutocomplete(params);
    };

    const [requestText, setRequestText] = useState(selectedRequestText());
    useEffect(() => {
        const text = props.selected_request_id === -1 ? '' : props.selected_request_id;
        fetchRequestsOnMapAutocomplete(text);
    }, []);
    useEffect(() => {
        setRequestText(selectedRequestText());
    }, [props.selected_request_id]);

    let timestampText = '';
    if (props.timestamp) {
        timestampText = 'на ' + moment(props.timestamp).format('HH:mm');
    }

    const onUpdateClick = () => {
        const map_location = localStorageService.get('map_location');
        props.fetchRequestsOnMap({ location: map_location });

        props.setSelectedMapRequestId(-1);
        fetchRequestsOnMapAutocomplete();
    };

    const onRequestTextChanged = (text) => {
        setRequestText(text);
        fetchRequestsOnMapAutocomplete(text);
    };

    const requestTypes = [
        { text: 'Опоздания', id: 'expiring_only' },
        { text: 'Задержка назначения', id: 'assignment_delay_only' },
    ];

    const onRequestTypeChanged = () => {
        const selectedRequestType = localStorageService.get('selected_request_on_map_type');
        props.setSelectedMapRequestType(selectedRequestType ? selectedRequestType : 'all');
    };
    useEffect(() => {
        onRequestTypeChanged();
    }, []);

    return (
        <ButtonsContainer
            left={
                <>
                    <span style={{ alignItems: 'center', display: 'flex' }}>
                        {titlePrefix(props.requestsNum)}
                    </span>
                    <CustomSelectWithStorage
                        options={locations.map((item) => item.text)}
                        values={locations.map((item) => item.id)}
                        defaultName='Филиал'
                        localStorageService={localStorageService}
                        updateData={() => {}}
                        optionName='map_location'
                    />
                    <span style={{ alignItems: 'center', display: 'flex' }}>{timestampText}</span>
                    <span onClick={onUpdateClick} className={styles.button}>
                        Обновить
                    </span>
                </>
            }
            right={
                <>
                    <span style={{ width: '200px', marginRight: '16px' }}>
                        <CustomSelectWithStorage
                            options={requestTypes.map((item) => item.text)}
                            values={requestTypes.map((item) => item.id)}
                            defaultName='Все'
                            localStorageService={localStorageService}
                            updateData={onRequestTypeChanged}
                            optionName='selected_request_on_map_type'
                        />
                    </span>
                    <span style={{ width: '240px' }}>
                        <CustomAutocomplete
                            options={props.delivery_requests_autocomplete}
                            value={requestText}
                            placeholder={'Заявка'}
                            onChange={onRequestTextChanged}
                            onIdChange={(id) => {
                                props.setSelectedMapRequestId(id);
                            }}
                            defaultId={props.selected_request_id}
                            disabled={false}
                        />
                    </span>
                </>
            }
        />
    );
};

const stateToProps = (state) => {
    let requests_autocomplete = [];
    const raw_autocomplete_data = state.requests_on_map.delivery_requests_autocomplete;
    if (raw_autocomplete_data) {
        requests_autocomplete = raw_autocomplete_data.results || [];
    }
    return {
        timestamp: state.requests_on_map.mapData.timestamp,
        requestsNum: state.requests_on_map.mapData.delivery_requests.length,
        delivery_requests_autocomplete: requests_autocomplete,
        selected_request_id: state.selected_request_on_map.id,
        selected_request_type: state.selected_request_on_map.request_type,
    };
};

const dispatchToProps = (dispatch) =>
    bindActionCreators(
        {
            fetchLocation,
            fetchRequestsOnMap,
            fetchRequestsOnMapAutocomplete,
            setSelectedMapRequestId,
            setSelectedMapRequestType,
        },
        dispatch
    );

export default connect(stateToProps, dispatchToProps)(Filters);
