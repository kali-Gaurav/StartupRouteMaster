from locust import HttpUser, task, between

class RouteSearchUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def search_routes(self):
        self.client.post(
            "/api/search_routes",
            json={
                "source": "Mumbai",
                "destination": "Goa",
                "date": "2025-12-25",
                "budget": "economy"
            }
        )
