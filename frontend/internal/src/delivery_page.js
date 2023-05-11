import React from 'react';
import ReactDOM from 'react-dom';
import { BrowserRouter as Router } from 'react-router-dom'
import DeliveryPage from './pages/DeliveryPage.jsx';

ReactDOM.render(
    (
        <Router>
            <DeliveryPage {...window.getPageProps()}/>
        </Router>
    ),
    document.getElementById('root')
);
