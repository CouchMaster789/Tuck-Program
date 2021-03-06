from datetime import datetime
from inherit_parent import Inherit
from accounts import Account
from products import Product
import math


class Transaction(Inherit):
    """loads provided transaction details into the object with ability to run the functions below on the object
    accordingly"""

    def __init__(self, transaction_id=None):
        """initialises transaction object with all attributes"""

        if transaction_id is not None:
            self._check_transaction_not("Transaction does not exist in database")

            transaction = \
                self._db_execute("SELECT * FROM transactions WHERE transaction_id = {0}".format(transaction_id))[0]
            transaction_id, account, amount, date, void = transaction
            products = \
                self._db_execute("SELECT * FROM transactions_products WHERE transaction_id = {0}".format(transaction_id)
                                 )
            quantity = [i[2] for i in products]
            products = [i[1] for i in products]
        else:
            account, products, quantity, amount, date, void = None, [], None, None, datetime.now(), None

        self.transaction_id = transaction_id
        self.account = account
        self.products = products
        self.quantity = quantity
        self.amount = amount
        self.date = datetime.now()
        self.void = void

    def record_transaction(self, account, *products):
        """records the transaction in the database"""

        if self.transaction_id is not None:
            raise RuntimeError("transaction_id must be set to None")
        if not isinstance(account, Account):
            raise RuntimeError("account parameter must be an instance of Account")
        if not any(isinstance(product, list) for product in products):
            raise ValueError("All products must be instances of list")
        if not any(self._is_len(product, 2) for product in products):
            raise ValueError("All products must be lists of length 2")
        if not any(isinstance(product, Product) for product in [product[0] for product in products]):  # check is done
            # outside of the coming for loop to prevent unnecessary working being done
            raise RuntimeError("products parameter must be a list with all first items being an instance of Product")
        if not any(isinstance(quantity, int) for quantity in [quantity[1] for quantity in products]):
            raise RuntimeError("products parameter must be a list with all second values being an instance of int")

        products_discount, total_amount = float(), float()

        for product, quantity in products:
            # product purchase limit
            for purchase_limit in product.purchase_limit:
                if purchase_limit[1] == "transaction":
                    if quantity > purchase_limit[0]:
                        raise ValueError("There is a purchase limit of \"{0}\" on product \"{1}\""
                                         "".format(purchase_limit[0], product.name))
                # must add further if statements

            amount = product.selling_price * quantity
            # product discount
            for discount in product.discount:
                products_discount += discount[0] if discount[1] == 0 else discount[0] / 100 * amount

            # product offer  # note: product.offers is a list with variables buy_x, get_y, z_off at positions 1,2,3
            # respectively
            for offer in product.offers:
                appliable = math.floor(quantity / (offer[0] + offer[1])) * offer[1]  # no. of items to apply z_off to
                amount -= appliable * (offer[2] / 100) if offer[3] == 0 \
                    else appliable * product.selling_price * (offer[2] / 100)

            total_amount += amount

        account_discount = float()

        # account discount
        for discount in account.discount:
            account_discount += discount[0] if discount[1] == 1 else discount[0] / 100 * total_amount

        total_to_pay = total_amount - products_discount - account_discount

        # check spending limit
        for spending_limit in account.spending_limit:
            error_msg = "Total payable is over the account spending limit of {0} per {1} by ".format(spending_limit[0], spending_limit[1])
            if spending_limit[1] == "transaction":
                if spending_limit[0] < total_to_pay:
                    raise ValueError(error_msg + "{0}".format(total_to_pay - account.spending_limit[0]))
            elif spending_limit[1] in ["day", "week", "month", "year"]:
                period_transactions = self._db_execute("SELECT amount FROM transactions WHERE account_id = {0} AND "
                                                       "date > date(\"now\", \"-1 {1}\")".format(1, spending_limit[1]))
                period_transactions = [transaction[0] for transaction in period_transactions]
                if sum(period_transactions) + total_to_pay > spending_limit[0]:
                    raise ValueError(error_msg + "{0}".format(period_transactions + total_to_pay - spending_limit[0]))

        # check sub zero allowance
        new_balance = account.balance - total_to_pay

        try:
            if new_balance < -account.sub_zero_allowance[0][0]:  # check out these [0]s
                raise ValueError("Not enough money in the account. New balance would be £{0} but the sub zero allowance"
                                 " is only £{1}.".format(new_balance, -account.sub_zero_allowance[0]))
        except IndexError:
            pass

        # perform transaction
        self._db_execute("INSERT INTO transactions VALUES (NULL, ?, ?, ?, ?)",
                         (account.account_id, total_to_pay, datetime.now(), False))
        for product in products:
            self._db_execute("INSERT INTO transactions_products VALUES (?, ?, ?)",
                             (self._get_last_id("transactions"), product[0].product_id, product[1]))
            product[0].update_details(quantity=-product[1])
        account.update_details(balance=-total_to_pay)

    def revert_transaction(self, transaction_id):
        """reverts the transaction in database by voiding it and then reverting its effects (refunding etc.)"""

        self._db_execute("UPDATE transactions SET void=1 WHERE transaction_ID={0}".format(transaction_id))
        account_id, amount = self._db_execute("SELECT account_id, amount FROM transactions "
                                              "WHERE transaction_ID={0}".format(transaction_id))[0]
        Account(account_id).update_details(balance=amount)
        for product_id, quantity in self._db_execute("SELECT product_ID, quantity FROM transactions_products "
                                                     "WHERE transaction_id={0}".format(transaction_id)):
            quantity += self._db_execute("SELECT quantity FROM products WHERE product_ID={0}".format(product_id))[0][0]
            self._db_execute("UPDATE products SET quantity={0} WHERE product_ID={1}".format(quantity, product_id))

    def _check_transaction_not(self, msg):
        """internal use only - checks if transaction exists, raising an error if it does"""

        if not self._check_item_exists("SELECT * FROM transactions WHERE transaction_id = {0}".format(
                self.transaction_id)):
            raise ValueError(msg)

    def _is_len(self, item, length):
        """internal use only - returns true if length of item is 2"""

        return len(item) == length


if __name__ == "__main__":
    couch = Transaction()
    # couch.record_transaction(Account(1), [Product(1), 4])
    couch.revert_transaction(1)
