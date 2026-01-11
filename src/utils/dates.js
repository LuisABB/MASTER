import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc.js';

dayjs.extend(utc);

/**
 * Get date range for trend analysis
 */
export function getDateRange(windowDays, baselineDays) {
  const endDate = dayjs().utc();
  const startDate = endDate.subtract(baselineDays, 'day');
  
  return {
    startDate: startDate.format('YYYY-MM-DD'),
    endDate: endDate.format('YYYY-MM-DD'),
    windowStartDate: endDate.subtract(windowDays, 'day').format('YYYY-MM-DD')
  };
}
