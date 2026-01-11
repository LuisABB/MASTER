import app from './app.js';
import logger from './utils/logger.js';

const PORT = process.env.PORT || 3000;
const NODE_ENV = process.env.NODE_ENV || 'development';

// Start server
const server = app.listen(PORT, () => {
  logger.info({
    port: PORT,
    env: NODE_ENV,
    nodeVersion: process.version
  }, 'Server started successfully');
  
  console.log(`\n🚀 Trends API is running!`);
  console.log(`📍 Environment: ${NODE_ENV}`);
  console.log(`🔗 URL: http://localhost:${PORT}`);
  console.log(`\n📚 Available endpoints:`);
  console.log(`   GET  /health              - Health check`);
  console.log(`   POST /v1/trends/query     - Query trends`);
  console.log(`   GET  /v1/regions          - List supported regions`);
  console.log(`\n💡 Press Ctrl+C to stop\n`);
});

// Graceful shutdown
const shutdown = async (signal) => {
  logger.info({ signal }, 'Shutdown signal received');
  
  server.close(() => {
    logger.info('HTTP server closed');
    process.exit(0);
  });

  // Force shutdown after 10 seconds
  setTimeout(() => {
    logger.error('Forced shutdown after timeout');
    process.exit(1);
  }, 10000);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.fatal({ error }, 'Uncaught exception');
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.fatal({ reason, promise }, 'Unhandled rejection');
  process.exit(1);
});

export default server;
