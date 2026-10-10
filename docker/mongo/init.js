db.createUser({
  user: "crm_reader",
  pwd: "crm_reader",
  roles: [{ role: "read", db: "crm" }],
});

db.createUser({
  user: "crm_writer",
  pwd: "crm_writer",
  roles: [{ role: "readWrite", db: "crm" }],
});
