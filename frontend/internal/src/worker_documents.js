import React from 'react';
import ReactDOM from 'react-dom';
import WorkerDocuments from './pages/WorkerDocuments.jsx';

ReactDOM.render(<WorkerDocuments {...window.getPageProps()}/>, document.getElementById('root'));
