import React from 'react';
import { withRouter } from 'react-router';

import 'moment/locale/ru';
import moment from 'moment';

import { Col } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';

import WrappedRangeForm from '../components/RangeForm.jsx';
import RemoteSelect from '../components/RemoteSelect.jsx';

import { getCookie } from '../utils/cookies.jsx';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class Photo extends React.Component {
    width = () => {
        if (this.props.compact) {
            return '240px';
        } else {
            return '640px';
        }
    }

    description = () => {
        let date = this.props.timestamp_as_date?
            moment(this.props.data.timestamp).format('DD.MM.YYYY HH:mm') :
            moment(this.props.data.date).format(DATE_FORMAT);
        if (this.props.compact) {
            return (
                <table width={this.width()}>
                    <tbody>
                        <tr><td>{date}</td></tr>
                        <tr><td>{this.props.data.worker_name}</td></tr>
                        <tr><td>{this.props.data.line}</td></tr>
                        <tr><td>{this.props.data.code}</td></tr>
                        <tr><td>{this.props.data.address}</td></tr>
                    </tbody>
                </table>
            );
        } else {
            return (
                <div>
                    [{date}] [{this.props.data.worker_name}] [{this.props.data.line}] [{this.props.data.code}] [{this.props.data.address}]
                </div>
            );
        }
    }

    render() {
        let src = this.props.data.photo?
            (this.props.urls.media_prefix + this.props.data.photo) : '/static/img/error.png';
        return (
            <div>
                {this.description()}
                <a
                    href={src}
                    target='_blank'
                >
                    <img
                        src={src}
                        width={this.width()}
                    />
                </a>
            </div>
        );
    }
}


class PhotoGlobalDashboard extends React.Component {
    constructor(props) {
        super(props);

        const params = new URLSearchParams(this.props.location.search);

        let worker = null;
        const worker_pk = params.get('worker');
        if (worker_pk) {
            worker = { key: worker_pk };
        }

        this.state = {
            worker: worker,

            request: params.get('request'),

            first_day: this.props.first_day,
            last_day: this.props.last_day,

            arrival_photos: [],
            turnout_photos: [],
        }

        this.fetchPhotos();
    }

    fetchPhotos = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.photos_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        if (this.state.request) {
            url.searchParams.set('request_pk', this.state.request);
        }
        if (this.state.worker) {
            url.searchParams.set('worker_pk', this.state.worker.key);
        }

        try {
            let response = await fetch(
                url,
                {
                    headers: new Headers({
                        'X-CSRFToken': getCookie('csrftoken'),
                    }),
                }
            );

            if (response.ok) {
                const body = await response.json();

                if (body.status === 'ok') {
                    this.setState(
                        {
                            fetching: false,
                            arrival_photos: body.arrival_photos,
                            turnout_photos: body.turnout_photos,
                        }
                    );
                    return;
                }
            }
        } catch (exception) {
            // nothing to do
        }
    }

    onWorkerChange = (value) => {
        this.setState({ worker: value});
    }

    onSubmitRange = (first_day, last_day) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day,

                arrival_photos: [],
                turnout_photos: [],
            },
            this.fetchPhotos
        );
    }

    photos = (photos, timestamp_as_date) => {
        let PHOTOS_IN_ROW = 5;
        let rows = [];
        let rows_count = photos.length / PHOTOS_IN_ROW;
        for (var i = 0; i < rows_count; ++i) {
            let cols = [];
            for (var j = 0; j < PHOTOS_IN_ROW; ++j) {
                let index = i * PHOTOS_IN_ROW + j;
                if (index < photos.length) {
                    cols.push(
                        <Col>
                            <Photo
                                urls={this.props.urls}
                                data={photos[index]}
                                timestamp_as_date={timestamp_as_date}
                                compact={this.state.request === null}
                            />
                        </Col>
                    );
                }
            }
            rows.push(
                <Row
                    type='flex'
                    gutter={[10, 30]}
                >
                    {cols}
                </Row>
            );
        }
        return rows;
    }

    arrivalPhotos = () => {
        if (this.state.arrival_photos.length > 0) {
            let rows = this.photos(this.state.arrival_photos, true);
            rows.unshift(
                <Row>
                    <Col><h4>Отметки о прибытии</h4></Col>
                </Row>
            );
            return rows;
        }
    }

    turnoutPhotos = () => {
        if (this.state.turnout_photos.length > 0) {
            let rows = this.photos(this.state.turnout_photos, false);
            rows.unshift(
                <Row>
                    <Col><h4>Фото табеля</h4></Col>
                </Row>
            );
            return rows;
        }
    }

    render() {
        let components = [];
        if (this.state.request === null) {
            components.push(
                <Row
                    type='flex'
                    gutter={[4, 12]}
                >
                    <Col
                        style={{ marginTop: '4px', marginRight: '14px' }}
                    >
                        <RemoteSelect
                            url={this.props.urls.worker_ac_url}
                            width='200px'
                            placeholder='Рабочий'
                            value={this.state.worker}
                            onChange={this.onWorkerChange}
                        />
                    </Col>
                    <Col>
                        <WrappedRangeForm
                            first_day={this.state.first_day}
                            last_day={this.state.last_day}
                            onSubmit={this.onSubmitRange}
                        />
                    </Col>
                </Row>
            );
        }
        components.push(
            <Row>
                <Col>
                    {this.arrivalPhotos()}
                    {this.turnoutPhotos()}
                </Col>
            </Row>
        );
        return components;
    }
}


export default withRouter(PhotoGlobalDashboard);
