// ponytail: one env file; production swaps in environment.prod.ts via angular.json fileReplacements
export const environment = {
  apiBase: 'http://localhost:8000', // Tenjin's API when running locally
  mock: true, // answer from src/app/api/mock-data.ts instead of the network
};
