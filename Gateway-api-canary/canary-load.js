import http from 'k6/http';
import { Counter, Rate } from 'k6/metrics';

const v1Requests = new Counter('v1_requests');
const v2Requests = new Counter('v2_requests');
const failedRequests = new Rate('failed_requests');

export const options = {
  scenarios: {
    canary_users: {
      executor: 'constant-vus',

      // Number of fake users
      vus: 20,

      // Keep users running continuously
      duration: '10m'
    }
  }
};

export default function () {
  const response = http.get('http://localhost:8081/', {
    headers: {
      Host: 'demo.example.com'
    }
  });

  if (response.status !== 200) {
    failedRequests.add(1);
    return;
  }

  failedRequests.add(0);

  if (response.body.includes('VERSION v1')) {
    v1Requests.add(1);
  }

  if (response.body.includes('VERSION v2')) {
    v2Requests.add(1);
  }
}
