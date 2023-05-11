import React from 'react';

import { Button } from 'antd';
import { Form } from 'antd';
import { Input } from 'antd';
import { Spin } from 'antd';

import { message } from 'antd';

import { getCookie } from '../utils/cookies.jsx';


class ImageButtons extends React.Component {

    onConfirm = () => {
        this.props.form.setFieldsValue({ 'comment': ' ' });

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onConfirm(values.hours);
            }
        );
    }

    onReject = () => {
        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onReject(values.comment);
            }
        );
    }

    hoursItem = () => {
        if (this.props.image.hours_required) {
            const key = 'hours';
            return (
                <Form.Item
                    key={key}
                    style={{ marginBottom: 0 }}
                    label='Отработано часов'
                >
                    {
                        this.props.form.getFieldDecorator(
                            key,
                            { rules: [{ required: true, message: 'Необходимо указать часы.' }] }
                        )(
                            <Input
                                placeholder='Отработано часов'
                                type='number'
                                min={this.props.image.min_hours}
                                step='0.1'
                                style={{ width: '120px' }}
                            />
                        )
                    }
                </Form.Item>
            );
        } else {
            return undefined;
        }
    }

    confirmItem = () => {
        return (
            <Form.Item key='confirm'>
                <Button
                    type='primary'
                    disabled={this.props.disabled}
                    onClick={this.onConfirm}
                >
                    Одобрить
                </Button>
            </Form.Item>
        );
    }

    commentItem = () => {
        const key = 'comment';
        return (
            <Form.Item
                key={key}
                style={{ marginBottom: 0 }}
            >
                {
                    this.props.form.getFieldDecorator(
                        key,
                        { rules: [{ required: true, message: 'Необходимо указать внятную причину отклонения!' }] }
                    )(
                        <Input
                            placeholder='Комментарий, почему отклонено'
                            type='text'
                            style={{ width: '480px' }}
                        />
                    )
                }
            </Form.Item>
        );
    }

    rejectItem = () => {
        return (
            <Form.Item key='reject'>
                <Button
                    type='primary'
                    disabled={this.props.disabled}
                    onClick={this.onReject}
                >
                    Отклонить
                </Button>
            </Form.Item>
        );
    }

    render() {
        return (
            <Form
                layout='inline'
            >
                {this.hoursItem()}
                {this.confirmItem()}
                {this.commentItem()}
                {this.rejectItem()}
            </Form>
        );
    }
}


const WrappedImageButtons = Form.create(
    {
        mapPropsToFields(props) {
            let result = {};
            if (!props.disabled && props.image.hours_required) {
                result.hours = Form.createFormField(
                    {
                        'value': props.image.min_hours
                    }
                );
            }

            return result;
        }
    }
)(ImageButtons);


class Image extends React.Component {
    constructor(props) {
        super(props)

        this.state = {
            finished: false
        }
    }

    onConfirm = (hours) => {
        this.makeAction('confirm', hours);
    }

    onReject = (comment) => {
        this.makeAction('reject', comment);
    }

    makeAction = async (action, value) => {
        this.setState({ finished: true });

        let url = null;
        if (action === 'confirm') {
            url = new URL(this.props.urls.confirm_photo_url, window.location);
            url.searchParams.set('pk', this.props.image.pk);
            url.searchParams.set('type', this.props.image.type);
            if (value) {
                url.searchParams.set('hours', value);
            }
        } else if (action === 'reject') {
            url = new URL(this.props.urls.reject_photo_url, window.location);
            url.searchParams.set('pk', this.props.image.pk);
            url.searchParams.set('type', this.props.image.type);
            url.searchParams.set('comment', value);
        }

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
                    return
                }
            }
        } catch (exception) {
            // nothing to do
        }

        this.setState({ finished: false });
        message.error({ content: 'Что-то пошло не так. Попробуйте еще.' });
    }

    buttonsBlock = () => {
        return (
            <WrappedImageButtons
                disabled={this.state.finished}
                image={this.props.image}
                onConfirm={this.onConfirm}
                onReject={this.onReject}
            />
        );
    }

    render() {
        let table_content = [];
        for (let [key, value] of Object.entries(this.props.image.descr)) {
            table_content.push(
                <tr><th>{key}</th><td>{value}</td></tr>
            );
        }
        let arrival_photos_block = null;
        if (this.props.image.arrival_photos && this.props.image.arrival_photos.length > 0) {
            arrival_photos_block = this.props.image.arrival_photos.map(
                item => (<div><img src={item.url}/></div>)
            );
        }
        const keys = [
            'Дата',
            'Рабочий',
            'Заявка',
            'Индекс',
            'Адрес'
        ];
        const table_short_content = keys.map(
            key => ('[' + this.props.image.descr[key] + ']')
        ).join(' ');
        return (
            <div>
                <div>
                    <table className='table rh-table table-hover'>
                        {table_content}
                    </table>
                </div>
                {arrival_photos_block}
                <div>{table_short_content}</div>
                <div>
                    <img src={this.props.image.url}/>
                </div>
                <div>
                    {this.buttonsBlock()}
                </div>
            </div>
        );
    }
}


export class PhotoCheckingPage extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            error: false,
            fetching: true,

            images: { arrival: [], timesheet: []},
        }

        this.fetchImages();
    }

    fetchImages = async () => {
        let url = new URL(this.props.urls.photos_to_check_url, window.location);
        url.searchParams.set('pk', this.props.delivery_request_pk);

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
                            images: body.data,
                        }
                    );
                    return;
                }
            }
        } catch (exception) {
            // nothing to do
        }

        this.setState({ error: true });
    }

    render() {
        if (this.state.error) {
            return 'Что-то пошло не так :( Подождите и обновите страницу.';
        }
        if (this.state.fetching) {
            return (
                <Spin
                    size='large'
                    spinning={true}
                    style={{ width: '100%', paddingTop: '100px' }}
                />
            )
        }
        if (this.state.images.arrival.length + this.state.images.timesheet.length === 0) {
            return 'Новых фото нет.';
        }

        let components = [];
        if (this.state.images.arrival.length > 0) {
            components.push(<h3>Отметки о прибытии</h3>);
            this.state.images.arrival.forEach(
                image => components.push(
                    <Image
                        urls={this.props.urls}
                        image={image}
                    />
                )
            );
        }
        if (this.state.images.timesheet.length > 0) {
            components.push(<h3>Фото табеля</h3>);
            this.state.images.timesheet.forEach(
                image => components.push(
                    <Image
                        urls={this.props.urls}
                        image={image}
                    />
                )
            );
        }
        return components;
    }
}
