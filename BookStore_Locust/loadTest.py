from locust import HttpUser, SequentialTaskSet, task, between
import json
import random
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from utilities.csvreader import CSVReader

data_folder = os.path.join(root_dir, "data")
json_file_path = os.path.join(data_folder, "books.json")
file_path = os.path.join(data_folder, "bookStoreCredentials.csv")


class UserBehaviour(SequentialTaskSet):

    def __init__(self, parent):
        super().__init__(parent)
        self.token = ""
        self.user_id = ""
        self.book_isbn_one = ""
        self.book_isbn_two = ""
        self.user_name = ""
        self.password = ""

        with open(json_file_path, "r") as file_object:
            self.data = json.load(file_object)
            file_object.close()

    def chooseRandomIsbn(self):
        random_index = random.choice(range(0, len(list(self.data['books']))))
        return str(self.data['books'][random_index]['isbn'])

    def on_start(self):
        my_user = self.parent.my_user_data.pop()
        self.user_name = my_user["UserName"]
        self.password = my_user["Password"]
        self.parent.my_user_data.insert(0, {'UserName': self.user_name, 'Password': self.password})

        creds = {
            "userName": f"{self.user_name}",
            "password": f"{self.password}"
        }

        respCreateUser = self.client.post("Account/v1/User",
                                          json=creds,
                                          name="Create User")

        jsonRespCreateUser = json.loads(respCreateUser.text)
        self.user_id = jsonRespCreateUser["userID"]

        respAuth = self.client.post("Account/v1/GenerateToken",
                                    json=creds,
                                    name="Authorization")

        jsonRespAuth = json.loads(respAuth.text)
        self.token = jsonRespAuth["token"]

    @task()
    def getUserInfo(self):
        self.client.get(f"Account/v1/User/{self.user_id}",
                        headers={
                            "Authorization": "Bearer %s" % self.token},
                        name="Get User info")

    @task()
    def getListOfBook(self):
        self.client.get("BookStore/v1/Books",
                        name="Get the list of books")

    @task()
    def getBookInfo(self):
        self.client.get('BookStore/v1/Book?ISBN='+self.chooseRandomIsbn(),
                        name="Get a book info")

    @task()
    def addBookToCart(self):
        self.book_isbn_one = self.chooseRandomIsbn()

        payload = {
            "userId": f"{self.user_id}",
            "collectionOfIsbns": [
                {
                    "isbn": f"{self.book_isbn_one}"
                }
            ]
        }

        self.client.post("BookStore/v1/Books",
                         headers={
                             "Authorization": "Bearer %s" % self.token
                         },
                         json=payload,
                         name="Add a book to cart")

    @task()
    def replaceBook(self):
        self.book_isbn_two = self.chooseRandomIsbn()
        while self.book_isbn_two == self.book_isbn_one:
            self.book_isbn_two = self.chooseRandomIsbn()

        payload = {
            "userId": f"{self.user_id}",
            "isbn": f"{self.book_isbn_two}"
        }

        self.client.put("BookStore/v1/Books/" + self.book_isbn_one,
                        headers={
                            "Authorization": "Bearer %s" % self.token
                        },
                        data=payload,
                        name="Replace the book in cart")

    @task()
    def deleteBook(self):
        payload = {
            "isbn": f"{self.book_isbn_two}",
            "userId": f"{self.user_id}"
        }

        self.client.delete("BookStore/v1/Book",
                           headers={
                               "Authorization": "Bearer %s" % self.token
                           },
                           json=payload,
                           name="Delete a book from the cart")

    @task()
    def deleteBooks(self):
        self.client.delete('BookStore/v1/Books?UserId=' + self.user_id,
                           headers={
                               "Authorization": "Bearer %s" % self.token
                           },
                           name="Delete all books from the cart")

    def on_stop(self):
        self.client.delete(f"Account/v1/User/{self.user_id}",
                           headers={
                               "Authorization": "Bearer %s" % self.token
                           },
                           name="Delete User")


class WebsiteUser(HttpUser):
    tasks = [UserBehaviour]
    host = "https://demoqa.com/"
    wait_time = between(2, 3)
    my_user_data = CSVReader(file_path).read_data()
