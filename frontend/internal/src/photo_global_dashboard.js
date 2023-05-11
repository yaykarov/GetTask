import React from 'react';
import ReactDOM from 'react-dom';
import {BrowserRouter as Router} from 'react-router-dom'
import PhotoGlobalDashboard from './pages/PhotoGlobalDashboard.jsx';

ReactDOM.render(
    (
        <Router>
            <PhotoGlobalDashboard {...window.getPageProps()}/>
        </Router>
    ),
    document.getElementById('root')
);
