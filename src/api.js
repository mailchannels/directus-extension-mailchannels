import { request } from 'directus:api';
import { createHandler } from './handler.js';

export default {
  id: 'mailchannels-send-email',
  handler: createHandler(request),
};
