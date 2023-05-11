import React from 'react';

import { DataTable } from './DataTable.jsx';


// Todo: merge with ContractsList?
export class ContractsTable extends React.Component {
    constructor(props) {
        super(props);

        this.data_table = React.createRef();
    }

    checked = () => {
        return this.data_table.current.checked;
    }

    processData = (json) => {
        let data = json.data;
        for (let i = 0; i < data.length; ++i) {
            const pk = data[i].worker_data.pk;
            const name = data[i].worker_data.full_name;
            const details_url = this.props.urls.worker_details_url_template.replace('12345', pk);

            data[i].worker = (
                '<a href="' + details_url + '" target="_blank">' + name + '</a>'
            );

            if (!data[i].number) {
                data[i].number = '-';
            }
            if (!data[i].begin_date) {
                data[i].begin_date = '-';
            }
            if (!data[i].end_date) {
                data[i].end_date = '-';
            }
        }
        return data;
    }

    render() {
        return (
            <DataTable
                ref={this.data_table}
                columns={this.props.columns}
                data_url={this.props.urls.contracts_list_dt_url}
                data_process={this.processData}
                data_extra={this.props.data_extra}
                enable_checkboxes={true}
            />
        );
    }
}

