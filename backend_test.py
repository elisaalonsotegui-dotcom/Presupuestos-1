import requests
import sys
import json
import io
import pandas as pd
from datetime import datetime

class BudgetAppTester:
    def __init__(self, base_url="https://budget-genius-23.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        if files:
            headers.pop('Content-Type', None)  # Let requests set it for multipart

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if not success:
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                    details += f", Error: {error_detail}"
                except:
                    details += f", Response: {response.text[:200]}"

            self.log_test(name, success, details)
            
            if success:
                try:
                    return response.json()
                except:
                    return {}
            return None

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return None

    def test_user_registration(self):
        """Test user registration"""
        timestamp = datetime.now().strftime('%H%M%S')
        test_user = {
            "email": f"test_user_{timestamp}@example.com",
            "username": f"test_user_{timestamp}",
            "password": "TestPass123!"
        }
        
        response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data=test_user
        )
        
        if response and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            return True
        return False

    def test_user_login(self):
        """Test user login with existing credentials"""
        # Try to login with the registered user
        if not self.token:
            return False
            
        # Test the /auth/me endpoint to verify token works
        response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return response is not None

    def test_product_creation(self):
        """Test manual product creation"""
        test_product = {
            "name": "Camiseta Básica",
            "description": "Camiseta de algodón 100% para personalización",
            "base_price": 12.50,
            "category": "Textil",
            "characteristics": {
                "material": "Algodón",
                "tallas": ["S", "M", "L", "XL"],
                "colores": ["Blanco", "Negro", "Azul"]
            }
        }
        
        response = self.run_test(
            "Create Product",
            "POST",
            "products",
            200,
            data=test_product
        )
        return response is not None

    def test_excel_upload(self):
        """Test Excel file upload for products"""
        # Create a sample Excel file in memory
        data = {
            'nombre': ['Taza Cerámica', 'Bolígrafo Metálico', 'Libreta A5'],
            'descripcion': ['Taza de cerámica blanca 350ml', 'Bolígrafo metálico con grabado', 'Libreta tapa dura A5'],
            'precio': [8.50, 3.20, 12.00],
            'categoria': ['Promocional', 'Escritura', 'Papelería'],
            'caracteristicas': [
                '{"capacidad": "350ml", "material": "cerámica"}',
                '{"material": "metal", "tinta": "azul"}',
                '{"páginas": 200, "tapa": "dura"}'
            ]
        }
        
        df = pd.DataFrame(data)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        files = {
            'file': ('test_products.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        }
        
        response = self.run_test(
            "Upload Excel Products",
            "POST",
            "products/upload-excel",
            200,
            files=files
        )
        return response is not None

    def test_get_products(self):
        """Test getting products list"""
        response = self.run_test(
            "Get Products List",
            "GET",
            "products",
            200
        )
        return response is not None

    def test_marking_technique_creation(self):
        """Test creating marking techniques"""
        techniques = [
            {
                "name": "Bordado",
                "cost_per_unit": 2.50,
                "description": "Bordado personalizado con hilo de alta calidad"
            },
            {
                "name": "Serigrafía",
                "cost_per_unit": 1.80,
                "description": "Impresión serigráfica para grandes cantidades"
            }
        ]
        
        success_count = 0
        for technique in techniques:
            response = self.run_test(
                f"Create Marking Technique - {technique['name']}",
                "POST",
                "marking-techniques",
                200,
                data=technique
            )
            if response:
                success_count += 1
        
        return success_count == len(techniques)

    def test_get_marking_techniques(self):
        """Test getting marking techniques list"""
        response = self.run_test(
            "Get Marking Techniques",
            "GET",
            "marking-techniques",
            200
        )
        return response is not None

    def test_quote_generation(self):
        """Test quote generation"""
        quote_data = {
            "client_name": "Empresa Test S.L.",
            "search_criteria": {
                "category": "Textil"
            },
            "marking_techniques": ["Bordado", "Serigrafía"]
        }
        
        response = self.run_test(
            "Generate Quote",
            "POST",
            "quotes/generate",
            200,
            data=quote_data
        )
        
        if response:
            # Verify quote structure
            required_fields = ['id', 'client_name', 'total_basic', 'total_medium', 'total_premium']
            has_all_fields = all(field in response for field in required_fields)
            self.log_test("Quote Structure Validation", has_all_fields, 
                         "Missing fields" if not has_all_fields else "All required fields present")
            return has_all_fields
        return False

    def test_get_quotes(self):
        """Test getting quotes history"""
        response = self.run_test(
            "Get Quotes History",
            "GET",
            "quotes",
            200
        )
        return response is not None

    def test_get_quote_details(self):
        """Test getting specific quote details"""
        # First get all quotes to get an ID
        quotes_response = self.run_test(
            "Get Quotes for Detail Test",
            "GET",
            "quotes",
            200
        )
        
        if quotes_response and len(quotes_response) > 0:
            quote_id = quotes_response[0]['id']
            response = self.run_test(
                "Get Quote Details",
                "GET",
                f"quotes/{quote_id}",
                200
            )
            return response is not None
        else:
            self.log_test("Get Quote Details", False, "No quotes available to test details")
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Budget App Backend Tests")
        print("=" * 50)
        
        # Authentication tests
        if not self.test_user_registration():
            print("❌ Registration failed, stopping tests")
            return False
            
        self.test_user_login()
        
        # Product management tests
        self.test_product_creation()
        self.test_excel_upload()
        self.test_get_products()
        
        # Marking techniques tests
        self.test_marking_technique_creation()
        self.test_get_marking_techniques()
        
        # Quote generation tests
        self.test_quote_generation()
        self.test_get_quotes()
        self.test_get_quote_details()
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        print(f"✅ Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        # Print failed tests
        failed_tests = [result for result in self.test_results if not result['success']]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = BudgetAppTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())