import React from 'react';

import { Form } from 'antd';
import { Select } from 'antd';
import { Spin } from 'antd';


class RemoteSelect extends React.Component {
    constructor(props) {
        super(props);

        this.lastFetchId = 0;

        this.state = {
            data: [],
            fetching: false,
            query: '',
            page: 1,
            more: true,
        };
    }

    fetchData = () => {
        this.lastFetchId += 1;
        const fetchId = this.lastFetchId;
        let url = new URL(this.props.url, window.location);
        url.searchParams.set('page', this.state.page);
        if (this.state.query) {
            url.searchParams.set('q', this.state.query);
        }
        if (this.props.forward) {
            url.searchParams.set(
                'forward',
                JSON.stringify(this.props.forward)
            );
        }
        fetch(
            url
        ).then(
            async (response) => {
                if (!response.ok) {
                    return;
                }
                if (fetchId !== this.lastFetchId) {
                    return;
                }
                let body = await response.json();

                this.setState(
                    (state, props) => {
                        return {
                            data: state.data.concat(body.results || []),
                            fetching: false,
                            more: body.pagination.more,
                        };
                    }
                );
            }
        )
    }

    fetchInitial = (value) => {
        this.setState(
            {
                data: [],
                fetching: true,
                query: value,
                page: 1,
                more: true
            },
            this.fetchData
        );
    }

    fetchNextPage = () => {
        this.setState(
            (state, props) => {
                return {
                    fetching: true,
                    page: state.page + 1
                };
            },
            this.fetchData
        );
    }

    handleChange = (value) => {
        if (this.props.onChange) {
            this.props.onChange(value);
        }
    }

    onPopupScroll = (e) => {
        if (!this.state.more || this.state.fetching) {
            return;
        }

        e.persist();
        const target = e.target;
        const delta = target.scrollHeight - target.offsetHeight - target.scrollTop;
        if (delta < 12) {
            this.fetchNextPage();
        }
    }

    render() {
        let options = this.state.data.map(
            d => {
                return <Select.Option key={d.id} title={d.text}>{d.text}</Select.Option>;
            }
        );
        if (this.state.more) {
            options.push(
                <Select.Option key='spinner' disabled><Spin size='small' /></Select.Option>
            );
        }
        if (options.length === 0) {
            options.push(
                <Select.Option key='nothing_found' disabled>ничего не найдено</Select.Option>
            );
        }
        return (
            <Select
                allowClear
                filterOption={false}
                labelInValue
                notFoundContent={this.state.fetching ? <Spin size="small" /> : null}
                onChange={this.handleChange}
                onFocus={this.fetchInitial}
                onSearch={this.fetchInitial}
                placeholder={this.props.placeholder}
                showSearch
                style={ this.props.width? { width: this.props.width } : {}}
                value={this.props.value || []}
                onPopupScroll={this.onPopupScroll}
                {...(this.props.extra_select_options || {})}
            >
            {options}
            </Select>
        );
    }
}


export function remoteSelectItem(
        form,
        key,
        label,
        url,
        width,
        show_labels,
        forward,
        optional
    ) {
    return (
        <Form.Item
            key={key}
            style={{ marginBottom: 0 }}
            label={show_labels? label : undefined}
        >
            {
                form.getFieldDecorator(
                    key,
                    { rules: [{ required: !optional, message: 'Это поле необходимо!' }] }
                )(
                    <RemoteSelect
                        url={url}
                        placeholder={label}
                        width={width}
                        forward={forward}
                    />
                )
            }
        </Form.Item>
    );
}

export default RemoteSelect;
