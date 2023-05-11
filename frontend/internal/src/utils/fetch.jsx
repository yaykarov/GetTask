export class SingleJsonFetcher {
    constructor() {
        this.lastFetchId = 0;
    }

    fetch = async (url, data) => {
        this.lastFetchId += 1;
        const fetch_id = this.lastFetchId;

        try {
            let response = await fetch(url, data);

            if (fetch_id !== this.lastFetchId) {
                // Todo: exception?
                return null;
            }
            if (!response.ok) {
                return {
                    message: 'Что-то пошло не так.'
                };
            }

            if (response.headers.get('Content-Type') === 'application/json') {
                return await response.json();
            } else {
                return await response.blob();
            }
        } catch (exception) {
            return {
                message: 'Что-то пошло не так. Проблемы с интернетом?'
            };
        }
    }
}

