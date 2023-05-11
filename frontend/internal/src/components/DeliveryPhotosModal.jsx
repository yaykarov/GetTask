import React from 'react';

import { Button } from 'antd';
import { Icon } from 'antd';
import { Modal } from 'antd';
import { Upload } from 'antd';

import { getCookie } from '../utils/cookies.jsx';


class DeliveryPhotosModal extends React.Component {
    content = () => {
        if (!this.props.workers) {
            return undefined;
        }

        let rows = this.props.workers.map(
            worker => (
                <tr>
                    <td
                        key='name'
                    >
                        <a
                            href={this.props.urls.photos_url_template.replace('12345', worker.pk)}
                            target='_blank'
                        >
                            {worker.label}
                        </a>
                    </td>
                    <td
                        key='upload'
                    >
                        <Upload
                            name='photos'
                            action={this.props.urls.add_photo_url_template.replace('12345', worker.pk)}
                            headers={{ 'X-CSRFToken': getCookie('csrftoken') }}
                            showUploadList={true}
                            multiple
                        >
                            <Button><Icon type='upload' />добавить фото</Button>
                        </Upload>
                    </td>
                </tr>
            )
        );
        return (
            <table>
                <tbody>
                    {rows}
                </tbody>
            </table>
        );
    }

    render() {
        return (
            <Modal
                visible={this.props.visible}
                title='Фото табелей'
                onCancel={this.props.onCancel}
                footer={null}
            >
                {this.content()}
            </Modal>
        );
    }
}


export default DeliveryPhotosModal;
