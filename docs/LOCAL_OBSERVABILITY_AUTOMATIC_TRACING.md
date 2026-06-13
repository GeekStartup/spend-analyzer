# Automatic Tracing Notes

Issue #78 uses automatic infrastructure tracing only:

- incoming FastAPI requests are traced centrally;
- outbound HTTP calls made with `requests` are traced centrally;
- application routes and services do not create manual spans;
- custom business spans are deferred to separate work.

Use the `request_id` returned in every Problem Details response to find the corresponding structured logs. When tracing is active, those logs contain `trace_id` and `span_id`, which can be used to inspect the trace in Tempo.

Database health currently uses the incoming HTTP trace and the bounded database dependency gauge. Dedicated Psycopg automatic instrumentation is separate work.
