

class Error(Exception):
    pass


class MigException(Error):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "Миграционная карта не заполнена: "+self.value+" отсутствует"

    def get_value(self):
        return self.value


class ContractException(Error):
    def __init__(self, id=None, value=None):
        self.contract_id = id
        self.value = value
    
    def __str__(self):
        return "Нет заключенных контрактов"

    def get_contract(self):
        return self.contract_id

    def get_value(self):
        return self.value


class WorkerException(Error):
    def __init__(self, id, value):
        self.worker_id = id
        self.value = value

    def __str__(self):
        return "Данные работника не заполнены: " + ",".join(self.value)

    def get_value(self):
        return self.value

    def get_worker(self):
        return self.worker_id
