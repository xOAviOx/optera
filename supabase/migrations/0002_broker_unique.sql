-- One broker connection per (user, broker) so the engine can upsert on reconnect.
alter table public.broker_connections
  add constraint broker_connections_user_broker_key unique (user_id, broker);
