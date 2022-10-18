from datetime import date


class Invoice:
    def __init__(
        self, company_name: str, client_name: str, start_date: date, end_date: date
    ):
        self.invoice_number = 1
        self.invoice_date = date.today()
        self.company = Company(company_name)
        self.client = Client(client_name)
        self.start_date = start_date
        self.end_date = end_date
        self.time_entries = self.get_time_entries(self.start_date, self.end_date)

    def get_time_entries(start_date, end_date):
        pass
        


class Company:
    def __init__(self, company_name: str):
        self.company_name = company_name
        self.email = "jordan.amos@gmail.com"
        self.abn = "47 436 539 044"
        self.rate = 70.00


class Client:
    def __init__(self, client_name: str):
        self.client_name = client_name
        self.client_contact = "John Scott"
        self.email = "john.scott@6cloudsystems.com"
