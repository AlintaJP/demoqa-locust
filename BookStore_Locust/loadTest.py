import logging

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

logger = logging.getLogger(__name__)

counter = 0


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

    @task()
    def createUser(self):
        global counter
        my_user = self.parent.my_user_data.pop()
        self.user_name = my_user["UserName"]
        if "100" in self.user_name:
            self.user_name = self.user_name.replace("100", "0")
            counter = 0
        else:
            self.user_name = self.user_name.replace(str(counter), str(counter+1))
            counter += 1
        self.password = my_user["Password"]
        self.parent.my_user_data.insert(0, {'UserName': self.user_name, 'Password': self.password})

        creds = {
            "userName": f"{self.user_name}",
            "password": f"{self.password}"
        }

        with self.client.post("Account/v1/User",
                              json=creds,
                              catch_response=True,
                              name="Create User") as respCreateUser:

            if "userID" not in respCreateUser.text:
                respCreateUser.failure("Failed to create User")
                logger.critical("Failed to create User \t" + self.user_name)
            else:
                jsonRespCreateUser = json.loads(respCreateUser.text)
                self.user_id = jsonRespCreateUser["userID"]
                respCreateUser.success()

        with self.client.post("Account/v1/GenerateToken",
                              json=creds,
                              catch_response=True,
                              name="Authorization") as respAuth:

            if "token" not in respAuth.text:
                respAuth.failure("Failed to authorize")
                logger.critical("Failed to authorize \t" + self.user_name)
            else:
                jsonRespAuth = json.loads(respAuth.text)
                self.token = jsonRespAuth["token"]
                respCreateUser.success()

    @task()
    def getUserInfo(self):
        with self.client.get(f"Account/v1/User/{self.user_id}",
                             headers={
                                 "Authorization": "Bearer %s" % self.token},
                             catch_response=True,
                             name="Get User info") as resp:

            if 'userId' not in resp.text:
                resp.failure("Failed to get User info")
                logger.error("Failed to get User info \t" + self.user_name)
            else:
                resp.success()

    @task()
    def getListOfBook(self):
        with self.client.get("BookStore/v1/Books",
                             catch_response=True,
                             name="Get the list of books") as resp:

            if "books" not in resp.text:
                resp.failure("Failed to get the list of books")
                logger.error("Failed to get the list of books \t" + self.user_name)
            else:
                resp.success()

    @task()
    def getBookInfo(self):
        with self.client.get('BookStore/v1/Book?ISBN=' + self.chooseRandomIsbn(),
                             catch_response=True,
                             name="Get book info") as resp:

            if "isbn" not in resp.text:
                resp.failure("Failed to get book info")
                logger.error("Failed to get book info \t" + self.user_name)
            else:
                resp.success()

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

        with self.client.post("BookStore/v1/Books",
                              headers={
                                  "Authorization": "Bearer %s" % self.token
                              },
                              json=payload,
                              catch_response=True,
                              name="Add a book to cart") as resp:

            if "isbn" not in resp.text:
                resp.failure("Failed to add the book to the cart")
                logger.error("Failed to add the book to the cart \t" + self.user_name)
            else:
                resp.success()

    @task()
    def replaceBook(self):
        self.book_isbn_two = self.chooseRandomIsbn()
        while self.book_isbn_two == self.book_isbn_one:
            self.book_isbn_two = self.chooseRandomIsbn()

        payload = {
            "userId": f"{self.user_id}",
            "isbn": f"{self.book_isbn_two}"
        }

        with self.client.put("BookStore/v1/Books/" + self.book_isbn_one,
                             headers={
                                 "Authorization": "Bearer %s" % self.token
                             },
                             data=payload,
                             catch_response=True,
                             name="Replace the book in cart") as resp:

            if 'userId' not in resp.text:
                resp.failure("Failed to update the book")
                logger.error("Failed to update the book \t" + self.user_name)
            else:
                resp.success()

    @task()
    def deleteBook(self):
        payload = {
            "isbn": f"{self.book_isbn_two}",
            "userId": f"{self.user_id}"
        }

        with self.client.delete("BookStore/v1/Book",
                                headers={
                                    "Authorization": "Bearer %s" % self.token
                                },
                                json=payload,
                                catch_response=True,
                                name="Delete a book from the cart") as resp:

            if resp.status_code != 204:
                resp.failure("Failed to delete the book")
                logger.error("Failed to delete the book \t" + self.user_name)
            else:
                resp.success()

    @task()
    def deleteBooks(self):
        with self.client.delete('BookStore/v1/Books?UserId=' + self.user_id,
                                headers={
                                    "Authorization": "Bearer %s" % self.token
                                },
                                catch_response=True,
                                name="Delete all books from the cart") as resp:

            if resp.status_code != 204:
                resp.failure("Failed to delete the books")
                logger.error("Failed to delete the books \t" + self.user_name)
            else:
                resp.success()

    @task()
    def deleteUser(self):
        with self.client.delete(f"Account/v1/User/{self.user_id}",
                                headers={
                                    "Authorization": "Bearer %s" % self.token
                                },
                                catch_response=True,
                                name="Delete User") as resp:

            if resp.status_code != 204:
                resp.failure("Failed to delete User")
                logger.error("Failed to delete User \t" + self.user_name)
            else:
                resp.success()


class WebsiteUser(HttpUser):
    tasks = [UserBehaviour]
    host = "https://demoqa.com/"
    wait_time = between(2, 3)
    my_user_data = CSVReader(file_path).read_data()
