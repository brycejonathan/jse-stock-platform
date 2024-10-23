// .github/actions/deployment-check/index.js
const core = require('@actions/core');
const https = require('https');

async function checkEndpoint(url, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, {
      timeout: timeout,
      headers: {
        'User-Agent': 'GitHub-Action-Deployment-Check'
      }
    }, (response) => {
      let data = '';
      
      response.on('data', (chunk) => {
        data += chunk;
      });

      response.on('end', () => {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve({
            statusCode: response.statusCode,
            data: data
          });
        } else {
          reject(new Error(`HTTP Status: ${response.statusCode}`));
        }
      });
    });

    request.on('error', (error) => reject(error));
    request.on('timeout', () => {
      request.destroy();
      reject(new Error('Request timed out'));
    });
  });
}

async function run() {
  try {
    // Get inputs
    const environment = core.getInput('environment', { required: true });
    const endpoints = core.getInput('endpoints', { required: true }).split(',');
    const maxRetries = parseInt(core.getInput('max-retries')) || 5;
    const retryDelay = parseInt(core.getInput('retry-delay')) || 30;

    core.info(`Starting deployment check for ${environment} environment`);
    core.info(`Checking endpoints: ${endpoints.join(', ')}`);

    const results = [];
    
    // Check each endpoint
    for (const endpoint of endpoints) {
      let retries = 0;
      let success = false;

      while (retries < maxRetries && !success) {
        try {
          core.info(`Checking endpoint ${endpoint} (Attempt ${retries + 1}/${maxRetries})`);
          await checkEndpoint(endpoint.trim());
          success = true;
          results.push({
            endpoint: endpoint,
            status: 'healthy',
            attempts: retries + 1
          });
          core.info(`✅ Endpoint ${endpoint} is healthy`);
        } catch (error) {
          retries++;
          if (retries === maxRetries) {
            results.push({
              endpoint: endpoint,
              status: 'unhealthy',
              error: error.message
            });
            throw new Error(`Failed to verify endpoint ${endpoint} after ${maxRetries} attempts: ${error.message}`);
          }
          core.info(`Attempt ${retries}/${maxRetries} failed, waiting ${retryDelay} seconds before retry...`);
          await new Promise(resolve => setTimeout(resolve, retryDelay * 1000));
        }
      }
    }

    // Set outputs
    core.setOutput('status', 'success');
    core.setOutput('timestamp', new Date().toISOString());
    core.setOutput('results', JSON.stringify(results));

  } catch (error) {
    core.setFailed(`Deployment check failed: ${error.message}`);
  }
}

run();