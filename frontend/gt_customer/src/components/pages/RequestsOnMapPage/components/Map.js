import React, { useEffect, useRef, useState } from 'react';

import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';

import { setSelectedMapRequestId, setSelectedMapRequestType } from '../../../../actions';

import {
    MapConsumer,
    MapContainer,
    Marker,
    Polygon,
    TileLayer,
    Tooltip,
    useMap,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { DomUtil, latLngBounds } from 'leaflet';

import moment from 'moment';

import './MapStyles.scss';

const ChangeView = (props) => {
    const { mapData, selection } = props;

    const map = useMap();
    const [firstCall, setIsFirstCall] = useState(true);

    const [minLL, setMinLL] = useState([55.754191, 37.620523]);
    const [maxLL, setMaxLL] = useState([55.754191, 37.620523]);

    const updateMapPosition = () => {
        const selectedWorker = selection?.worker || null;
        const selectedRequest = selection?.request || null;

        let minLat = null;
        let minLon = null;
        let maxLat = null;
        let maxLon = null;

        const locations = [];

        mapData.workers.forEach((worker) => {
            if (
                (selectedWorker !== null && selectedWorker.pk === worker.pk) ||
                (selectedRequest !== null && selectedRequest.workers?.includes(worker.pk)) ||
                (selectedWorker === null && selectedRequest === null)
            ) {
                locations.push(worker.location);
            }
        });
        mapData.delivery_requests.forEach((request) => {
            if (
                (selectedRequest !== null && selectedRequest.pk === request.pk) ||
                (selectedWorker !== null && selectedWorker.requests?.includes(request.pk)) ||
                (selectedWorker === null && selectedRequest === null)
            ) {
                request.items.forEach((item) => {
                    locations.push(item.location);
                });
            }
        });

        const bb = mapData?.bounding_box;
        if (locations.length === 0) {
            if (bb) {
                minLat = bb.min_latitude;
                minLon = bb.min_longitude;
                maxLat = bb.max_latitude;
                maxLon = bb.max_longitude;
            }
        } else {
            let avgLocation = null;
            if (bb) {
                avgLocation = {
                    latitude: (bb.min_latitude + bb.max_latitude) / 2,
                    longitude: (bb.min_longitude + bb.max_longitude) / 2,
                };
            }

            locations.forEach((location) => {
                const lat = location.latitude;
                const lon = location.longitude;

                if (
                    avgLocation &&
                    selectedWorker === null &&
                    selectedRequest === null &&
                    (Math.abs(lat - avgLocation.latitude) > 1.3 ||
                        Math.abs(lon - avgLocation.longitude) > 1.3)
                ) {
                    return;
                }

                if (minLat === null || lat < minLat) {
                    minLat = lat;
                }
                if (minLon === null || lon < minLon) {
                    minLon = lon;
                }
                if (maxLat === null || lat > maxLat) {
                    maxLat = lat;
                }
                if (maxLon === null || lon > maxLon) {
                    maxLon = lon;
                }
            });
        }

        if (minLat) {
            if (maxLat - minLat < 0.03) {
                maxLat = maxLat + 0.01;
                minLat = minLat - 0.01;
            }
            if (maxLon - minLon < 0.03) {
                maxLon = maxLon + 0.01;
                minLat = minLat - 0.01;
            }

            setMinLL([minLat, minLon]);
            setMaxLL([maxLat, maxLon]);
        }
    };

    useEffect(() => {
        updateMapPosition();
    }, [mapData, selection]);

    useEffect(() => {
        map.fitBounds([
            [minLL[0], minLL[1]],
            [maxLL[0], maxLL[1]],
        ]);
    }, [minLL, maxLL]);

    useEffect(() => {
        map.zoomControl.setPosition('topright');
    }, []);

    return null;
};

const MutableTooltip = ({ className, opacity, children }) => {
    const tooltipRef = useRef();

    useEffect(() => {
        const tooltip = tooltipRef.current;
        if (tooltip !== undefined) {
            tooltip.setOpacity(opacity);

            if (tooltip._container !== undefined) {
                const currentClassName = tooltip.options.className;
                if (currentClassName !== undefined && currentClassName != className) {
                    DomUtil.removeClass(tooltip._container, currentClassName);
                }
                tooltip.options.className = className;
                DomUtil.addClass(tooltip._container, className);
            }
        }
    });

    return (
        <Tooltip ref={tooltipRef} className={className} permanent={true} opacity={opacity}>
            {children}
        </Tooltip>
    );
};

const Map = (props) => {
    const deliveryRequests = () => {
        let filter = () => true;
        if (props.selected_request_type === 'expiring_only') {
            filter = (item) => item.expiring;
        }
        if (props.selected_request_type === 'assignment_delay_only') {
            filter = (item) => item.is_worker_assignment_delayed;
        }
        return props.mapData.delivery_requests.filter(filter);
    };

    const [selection, setSelection] = useState();

    useEffect(() => {
        setSelection(null, null);
    }, [props.mapData]);

    useEffect(() => {
        const request =
            deliveryRequests().find((item) => {
                return item.pk == props.selected_request_id;
            }) || null;
        const src_pk = selection ? (selection.request ? selection.request.pk : null) : null;
        const dst_pk = request ? request.pk : null;
        if (src_pk !== dst_pk) {
            setSelection({ worker: selection ? selection.worker : null, request });
        }
    }, [props.selected_request_id, props.mapData]);

    const changeSelection = (worker, request) => {
        if (worker === null && request === null) {
            setSelection(null);
            props.setSelectedMapRequestId(-1);
        } else {
            setSelection({ worker, request });
            props.setSelectedMapRequestId(request ? request.pk : -1);
        }
    };

    const clearSelection = () => {
        changeSelection(null, null);
    };

    const iconRed = '/icons/mapRedIcon.svg';
    const iconGreen = '/icons/mapGreenIcon.svg';
    const iconBlue = '/icons/mapBlueIcon.svg';

    const markerIconMap = (iconUrl, iconSize) => {
        return new L.Icon({
            iconUrl: iconUrl,
            iconRetinaUrl: iconUrl,
            popupAnchor: [0, -16],
            iconSize: iconSize,
        });
    };

    const requestIcon = (request) => {
        const icon = request.expiring ? iconRed : iconGreen;
        return markerIconMap(icon, requestIconSize(request));
    };

    const onWorkerClick = (worker) => {
        changeSelection(worker, null);
    };

    const onRequestClick = (request) => {
        changeSelection(null, request);
    };

    const isWorkerSelected = (worker) => {
        const selectedWorker = selection?.worker || null;
        const selectedRequest = selection?.request || null;

        if (selectedRequest !== null && selectedRequest.workers !== null) {
            if (selectedRequest.workers.includes(worker.pk)) {
                return true;
            }
        }
        if (selectedWorker !== null) {
            if (worker.pk === selectedWorker.pk) {
                return true;
            }
        }
        return false;
    };

    const isRequestSelected = (request) => {
        const selectedWorker = selection?.worker || null;
        const selectedRequest = selection?.request || null;

        if (selectedWorker !== null && selectedWorker.requests !== null) {
            if (selectedWorker.requests.includes(request.pk)) {
                return true;
            }
        }
        if (selectedRequest !== null) {
            if (request.pk === selectedRequest.pk) {
                return true;
            }
        }
        return false;
    };

    const largeIconSize = [24, 24];
    const mediumIconSize = [16, 16];
    const smallIconSize = [10, 10];

    const workerIconSize = (worker) => {
        const selectedWorker = selection?.worker || null;
        const selectedRequest = selection?.request || null;

        if (isWorkerSelected(worker)) {
            return largeIconSize;
        } else {
            if (selectedWorker === null && selectedRequest === null) {
                return mediumIconSize;
            } else {
                return smallIconSize;
            }
        }
    };

    const requestIconSize = (request) => {
        const selectedWorker = selection?.worker || null;
        const selectedRequest = selection?.request || null;

        if (isRequestSelected(request)) {
            return largeIconSize;
        } else {
            if (selectedWorker === null && selectedRequest === null) {
                return mediumIconSize;
            } else {
                return smallIconSize;
            }
        }
    };

    const tooltipOpacity = (isSelected) => {
        const selectedWorker = selection?.worker || null;
        const selectedRequest = selection?.request || null;

        if (isSelected) {
            return 0.9;
        } else {
            if (selectedWorker === null && selectedRequest === null) {
                return 0.6;
            } else {
                return 0.25;
            }
        }
    };

    const workerTooltip = (worker) => {
        const isSelected = isWorkerSelected(worker);
        const opacity = tooltipOpacity(isSelected);
        const timestamp = moment(worker.location.timestamp).format('HH:mm');
        let tooltipText = worker.last_name + ' ' + timestamp;
        let tooltipClass = 'tooltipBlue';
        if (isSelected) {
            tooltipText = worker.full_name + ' ' + worker.phone + ' ' + timestamp;
            tooltipClass = 'tooltipBlueSelected';
        }
        return (
            <MutableTooltip className={tooltipClass} opacity={opacity}>
                <div
                    style={{
                        margin: '0 auto',
                        fontSize: '12px',
                        textAlign: 'center',
                    }}
                >
                    {tooltipText}
                </div>
            </MutableTooltip>
        );
    };

    const requestTooltip = (request, item) => {
        const isSelected = isRequestSelected(request);
        const opacity = tooltipOpacity(isSelected);
        let tooltipText = request.confirmed_timepoint;
        let tooltipClass = 'tooltipRed';
        if (isSelected) {
            tooltipText =
                (request.confirmed_timepoint || '') +
                ' ' +
                request.pk +
                ' ' +
                item.code +
                ' ' +
                request.driver_full_name +
                ' ' +
                request.driver_phones;
            tooltipClass = 'tooltipRedSelected';
        }
        if (tooltipText) {
            return (
                <MutableTooltip className={tooltipClass} opacity={opacity}>
                    <div
                        style={{
                            margin: '0 auto',
                            fontSize: '12px',
                            textAlign: 'center',
                        }}
                    >
                        {tooltipText}
                    </div>
                </MutableTooltip>
            );
        } else {
            return null;
        }
    };

    return (
        <MapContainer
            style={{
                height: '82vh',
                width: '99%',
                margin: '10px',
                marginTop: '16px',
                zIndex: '0',
            }}
        >
            <MapConsumer>
                {(map) => {
                    map.on('click', clearSelection);
                    return null;
                }}
            </MapConsumer>
            <ChangeView
                mapData={{ ...props.mapData, delivery_requests: deliveryRequests() }}
                selection={selection}
            />
            <TileLayer url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' />
            {props.mapData.workers.map((item) => {
                return (
                    <Marker
                        position={[item.location.latitude, item.location.longitude]}
                        icon={markerIconMap(iconBlue, workerIconSize(item))}
                        key={item.pk}
                        eventHandlers={{ click: () => onWorkerClick(item) }}
                    >
                        {workerTooltip(item)}
                    </Marker>
                );
            })}
            {deliveryRequests().map((request) => {
                return request.items.map((item: any) => {
                    return (
                        <Marker
                            position={[
                                item.location.latitude !== null ? item.location.latitude : '',
                                item.location.longitude !== null ? item.location.longitude : '',
                            ]}
                            icon={requestIcon(request)}
                            key={item.pk}
                            eventHandlers={{ click: () => onRequestClick(request) }}
                        >
                            {requestTooltip(request, item)}
                        </Marker>
                    );
                });
            })}
            {props.mapData?.city_borders && (
                <Polygon
                    pathOptions={{ opacity: 0.9, fill: false }}
                    positions={props.mapData?.city_borders}
                />
            )}
        </MapContainer>
    );
};

const stateToProps = (state) => ({
    mapData: state.requests_on_map.mapData,
    selected_request_id: state.selected_request_on_map.id,
    selected_request_type: state.selected_request_on_map.request_type,
});

const dispatchToProps = (dispatch) =>
    bindActionCreators(
        {
            setSelectedMapRequestId,
            setSelectedMapRequestType,
        },
        dispatch
    );

export default connect(stateToProps, dispatchToProps)(Map);
