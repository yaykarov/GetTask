import React from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import { withRouter } from 'react-router-dom';
import Unfilled from './Unfilled';
import Filled from './Filled';
import { accountInfo } from '../../../actions';

function InfoPage({ registrationStatus }) {
    if (
        ['info_required', 'scan_required', 'confirmation_required'].some(
            (s) => registrationStatus === s
        )
    ) {
        return <Unfilled />;
    } else if (registrationStatus === 'completed') {
        return <Filled />;
    }
    return null;
}

const mapStateToProps = (state) => ({
    registrationStatus: state.user.info.registrationStatus,
    user: state.user,
});

const mapDispatchToProps = (dispatch) => bindActionCreators({ accountInfo }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(withRouter(InfoPage));
