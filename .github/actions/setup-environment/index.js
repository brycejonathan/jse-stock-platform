// .github/actions/setup-environment/index.js
const core = require('@actions/core');
const exec = require('@actions/exec');
const io = require('@actions/io');
const path = require('path');
const fs = require('fs').promises;

async function setupAwsCredentials(region) {
  try {
    const credentials = {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      region: region
    };

    if (!credentials.accessKeyId || !credentials.secretAccessKey) {
      throw new Error('AWS credentials not found in environment');
    }

    const awsDir = path.join(process.env.HOME, '.aws');
    await io.mkdirP(awsDir);

    const configContent = [
      '[default]',
      `region = ${region}`,
      'output = json'
    ].join('\n');

    const credentialsContent = [
      '[default]',
      `aws_access_key_id = ${credentials.accessKeyId}`,
      `aws_secret_access_key = ${credentials.secretAccessKey}`
    ].join('\n');

    await fs.writeFile(path.join(awsDir, 'config'), configContent);
    await fs.writeFile(path.join(awsDir, 'credentials'), credentialsContent);
    await exec.exec('chmod', ['-R', '600', awsDir]);

    return true;
  } catch (error) {
    throw new Error(`Failed to setup AWS credentials: ${error.message}`);
  }
}

async function setupEnvironmentVariables(environment) {
  try {
    const envFile = path.join(process.cwd(), `deployment/environments/${environment}/.env`);
    const envVars = await fs.readFile(envFile, 'utf8');
    
    const variables = envVars.split('\n')
      .filter(line => line && !line.startsWith('#'))
      .reduce((acc, line) => {
        const [key, value] = line.split('=').map(part => part.trim());
        if (key && value) {
          acc[key] = value;
        }
        return acc;
      }, {});

    Object.entries(variables).forEach(([key, value]) => {
      core.exportVariable(key, value);
    });

    return variables;
  } catch (error) {
    throw new Error(`Failed to setup environment variables: ${error.message}`);
  }
}

async function setupKubernetes(environment) {
  try {
    const kubeconfig = process.env.KUBECONFIG;
    if (!kubeconfig) {
      throw new Error('KUBECONFIG not found in environment');
    }

    // Update kubeconfig with cluster information
    await exec.exec('kubectl', ['config', 'use-context', environment]);
    
    // Verify connection
    await exec.exec('kubectl', ['cluster-info']);

    return true;
  } catch (error) {
    throw new Error(`Failed to setup Kubernetes: ${error.message}`);
  }
}

async function run() {
  try {
    // Get inputs
    const environment = core.getInput('environment', { required: true });
    const setupType = core.getInput('setup-type') || 'full';
    const awsRegion = core.getInput('aws-region') || 'us-east-1';

    core.info(`Setting up ${environment} environment (${setupType} setup)`);

    // Setup AWS credentials
    await setupAwsCredentials(awsRegion);
    core.info('✅ AWS credentials configured');

    // Setup environment variables
    const envVars = await setupEnvironmentVariables(environment);
    core.info('✅ Environment variables configured');

    // Setup Kubernetes if full setup
    if (setupType === 'full') {
      await setupKubernetes(environment);
      core.info('✅ Kubernetes configured');
    }

    // Set outputs
    core.setOutput('config', JSON.stringify(envVars));
    core.setOutput('timestamp', new Date().toISOString());

    core.info('Environment setup completed successfully');
  } catch (error) {
    core.setFailed(`Environment setup failed: ${error.message}`);
  }
}

run();