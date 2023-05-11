import React from 'react';

import { Button } from 'antd';
import { Col } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';

import { getCookie } from '../utils/cookies.jsx';


class DocumentPhoto extends React.Component {
    constructor(props) {
        super(props);

        console.log(this.props);

        this.state = {
            fetching: false,

            type: this.props.type,
        }
    }

    updatePhoto = async (type) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.update_photo_url, window.location);
        url.searchParams.set('worker', this.props.worker);
        url.searchParams.set('pk', this.props.pk);
        url.searchParams.set('type', type);

        try {
            let response = await fetch(
                url,
                {
                    method: 'POST',
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
                            type: body.photo.type,
                        }
                    );
                    return;
                }
            }
        } catch (exception) {
            // nothing to do
        }

        this.setState({ fetching: false });
    }

    controlBlock = () => {
        if (this.state.fetching) {
            return '...';
        } else {
            let components = [];

            if (this.state.type !== 'migration_card') {
                components.push(
                    <Button
                        type='primary'
                        style={{margin: '8px'}}
                        onClick={(e) => { this.updatePhoto('migration_card'); }}
                    >
                        Это фото миграционки
                    </Button>
                );
            }

            if (this.state.type !== 'passport') {
                components.push(
                    <Button
                        type='primary'
                        style={{margin: '8px'}}
                        onClick={(e) => { this.updatePhoto('passport'); }}
                    >
                        Это фото паспорта
                    </Button>
                );
            }

            if (this.state.type !== 'general') {
                components.push(
                    <Button
                        type='primary'
                        style={{margin: '8px'}}
                        onClick={(e) => { this.updatePhoto('general'); }}
                    >
                        Это фото другого документа
                    </Button>
                );
            }

            return components;
        }
    }

    render() {
        return (
            <div>
                <a
                    href={this.props.url}
                    target='_blank'
                >
                    <img
                        src={this.props.url}
                        width={'640px'}
                    />
                </a>
                {this.controlBlock()}
            </div>
        )
    }
}


class WorkerDocuments extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            fetching: false,

            photos: [],
        }

        this.fetchPhotos();
    }

    fetchPhotos = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.worker_documents_url, window.location);
        url.searchParams.set('worker', this.props.worker);

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
                            photos: body.photos,
                        }
                    );
                    return;
                }
            }
        } catch (exception) {
            // nothing to do
        }

        this.setState({ fetching: false });
    }

    render() {
        if (this.state.fetching) {
            return (
                <Row
                    key='spinner'
                    type='flex'
                >
                    <Col
                        span={24}
                    >
                        <Spin
                            size='large'
                            spinning={true}
                            style={{ width: '100%', paddingTop: '250px' }}
                        />
                    </Col>
                </Row>
            );
        } else {
            return this.state.photos.map(
                item => (
                    <DocumentPhoto
                        urls={this.props.urls}
                        worker={this.props.worker}
                        {...item}
                    />
                )
            )
            return 'wtf?'
        }
    }
}


export default WorkerDocuments;
