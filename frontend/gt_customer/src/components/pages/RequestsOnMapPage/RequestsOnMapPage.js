import React from 'react';

import { connect } from 'react-redux';

import Filters from './components/Filters';
import Map from './components/Map';
import Spinner from '../../Spinner/Spinner';
import Wrapper from '../../Wrapper/Wrapper';

const RequestsOnMapPage = (props) => {
    return (
        <Wrapper title='Заявки на карте'>
            <Filters />
            <Map />
            {props.isLoading && <Spinner />}
        </Wrapper>
    );
};

const stateToProps = (state) => ({
    isLoading: state.requests_on_map.isLoading,
});

export default connect(stateToProps)(RequestsOnMapPage);
