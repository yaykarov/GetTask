import React from 'react';
import ReactDOM from 'react-dom';
import { WorkersList } from './pages/WorkersList.jsx';

ReactDOM.render(<WorkersList {...window.getPageProps()}/>, document.getElementById('root'));
