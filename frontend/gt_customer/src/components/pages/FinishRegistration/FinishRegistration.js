import React, { useState, useEffect } from 'react';
import { Redirect } from 'react-router-dom';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import { accountInfo, finishRegistration } from '../../../actions';
import { getToken } from '../../../utils';

function FinishRegistration({ match, user, accountInfo, finishRegistration, location }) {
    const token = getToken();
    const { from } = (location && location.state) || { from: { pathname: '/info' } };
    const uid = match.params.uid;
    const [redirect, setRedirect] = useState(false);

    useEffect(() => {
        if (!token) {
            finishRegistration({ uid })
                .then((res) => {
                    localStorage.setItem('token', res.payload.data.access_token);
                    return accountInfo({ token: res.payload.data.access_token });
                })
                .then(() => {
                    setRedirect(true);
                });
        } else {
            setRedirect(true);
        }
    }, []);

    if (redirect) {
        return (
            <Redirect
                to={{
                    pathname: from.pathname,
                    state: { from: '/finish_registration' },
                }}
            />
        );
    }

    return null;
}

const mapStateToProps = (state) => ({
    user: state.user,
});

const mapDispatchToProps = (dispatch) =>
    bindActionCreators({ accountInfo, finishRegistration }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(FinishRegistration);
