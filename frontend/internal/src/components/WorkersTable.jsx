import React from 'react';

import { DataTable } from './DataTable.jsx';


// Todo: merge with WorkersList?
export class WorkersTable extends React.Component {
    processData = (json) => {
        let data = json.data;
        for (let i = 0; i < data.length; ++i) {
            const pk = data[i].worker_data.pk;
            const name = data[i].worker_data.full_name;
            const edit_url = this.props.urls.worker_edit_url_template.replace('12345', pk);
            const details_url = this.props.urls.worker_details_url_template.replace('12345', pk);
            data[i].worker = (
                '<a href="' + edit_url + '" target="_blank"><i class="far fa-edit"></i></a>' +
                '<span style="margin-left: 16px;"> </span>' +
                '<a href="' + details_url + '" target="_blank">' + name + '</a>'
            );
        }
        return data;
    }

    render() {
        return (
            <DataTable
                columns={this.props.columns}
                data_url={this.props.urls.workers_list_dt_url}
                data_process={this.processData}
            />
        );
    }
}
