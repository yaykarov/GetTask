import React, { memo, useEffect } from 'react';
import { BrowserRouter as Router, Switch, Route, Redirect } from 'react-router-dom';
import { createBrowserHistory } from 'history';
import { Provider, connect } from 'react-redux';
import thunk from 'redux-thunk';
import { createStore, applyMiddleware, bindActionCreators } from 'redux';
import 'react-date-range/dist/styles.css';
import 'react-date-range/dist/theme/default.css';
import reducer from './reducers';
import axios from 'axios';
import axiosMiddleware from 'redux-axios-middleware';
import styles from './App.module.css';
import { accountInfo } from './actions';
import Sidebar from './components/Sidebar/Sidebar';
import RequestsPage from './components/pages/RequestsPage/RequestsPage';
import RequestsOnMapPage from './components/pages/RequestsOnMapPage/RequestsOnMapPage';
import ReportsPage from './components/pages/ReportsPage/ReportsPage';
import ImportHistoryPage from './components/pages/ImportHistoryPage/ImportHistoryPage';
import InfoPage from './components/pages/InfoPage/InfoPage';
import BalancePage from './components/pages/BalancePage/BalancePage';
import LoginPage from './components/pages/LoginPage/LoginPage';
import DailyConfirmationPage from './components/pages/DailyConfirmation/DailyConfirmation';
import SignupPage from './components/pages/SignupPage/SignupPage';
import FinishRegistration from './components/pages/FinishRegistration/FinishRegistration';
import ResetPasswordPage from './components/pages/ResetPasswordPage/ResetPasswordPage';
import UpdatePasswordPage from './components/pages/UpdatePasswordPage/UpdatePasswordPage';
import { BACKEND_URL } from './utils/constants';
import { getToken, setToken } from './utils';

const client = axios.create({
    baseURL: `${BACKEND_URL}gt/customer/`,
    responseType: 'json',
});

const store = createStore(
    reducer,
    applyMiddleware(
        // axiosMiddleware(client, { returnRejectedPromiseOnError: true }),
        thunk
    )
);

const history = createBrowserHistory();

const mapStateToProps = (state) => ({
    user: state.user,
});
const PrivateRoute = connect(mapStateToProps)(
    memo(({ component: Component, children, user, ...rest }) => (
        <Route
            {...rest}
            render={(props) =>
                getToken() ? (
                    children
                ) : (
                    <Redirect
                        to={{
                            pathname: '/login',
                            state: { from: props.location },
                        }}
                    />
                )
            }
        />
    ))
);

const mapDispatchToProps = (dispatch) => bindActionCreators({ accountInfo }, dispatch);

const AutoLoaderUserInfo = connect(
    mapStateToProps,
    mapDispatchToProps
)(({ accountInfo }) => {
    useEffect(() => {
        (function reload() {
            if (getToken()) {
                accountInfo()
                    .then(() => setTimeout(() => reload(), 50000))
                    .catch((error) => setTimeout(() => reload(), 10000));
            }
        })();
    }, [getToken()]);

    return null;
});

function App() {
    return (
        <Provider store={store}>
            <AutoLoaderUserInfo />
            <Router history={history}>
                <div className={styles.App}>
                    <Switch>
                        <PrivateRoute exact path='/requests'>
                            <Sidebar menu='requests' />
                            <RequestsPage />
                        </PrivateRoute>
                        <PrivateRoute exact path='/requests_on_map'>
                            <Sidebar menu='requests_on_map' />
                            <RequestsOnMapPage />
                        </PrivateRoute>
                        <PrivateRoute exact path='/reports'>
                            <Sidebar menu='reports' />
                            <ReportsPage />
                        </PrivateRoute>
                        <PrivateRoute exact path='/info'>
                            <Sidebar menu='info' />
                            <InfoPage />
                        </PrivateRoute>
                        <PrivateRoute exact path='/imports'>
                            <Sidebar menu='imports' />
                            <ImportHistoryPage />
                        </PrivateRoute>
                        <PrivateRoute exact path='/balance'>
                            <Sidebar menu='balance' />
                            <BalancePage />
                        </PrivateRoute>

                        <Route exact path='/daily_reconciliation/:uid'>
                            <DailyConfirmationPage />
                        </Route>
                        <Route exact path='/login'>
                            <LoginPage />
                        </Route>
                        <Route exact path='/signup'>
                            <SignupPage />
                        </Route>
                        <Route exact path='/reset_password'>
                            <ResetPasswordPage />
                        </Route>
                        <Route exact path='/update_password/:uid'>
                            <UpdatePasswordPage />
                        </Route>
                        <Route path='/finish_registration/:uid' component={FinishRegistration} />
                        <Route path='/'>
                            <Redirect to='/requests' />
                        </Route>
                    </Switch>
                </div>
            </Router>
        </Provider>
    );
}

export default App;
