# Customer Management

A catalog Solution bundle: install it once into your own workspace, then stamp
one **Customer Success Agent** per customer relationship. Each stamped agent
serves a single customer — grounded in that customer's context, strictly in
that customer's scope, with a durable memory of the account.

## What ships

```
customer-management/
├── sample.yaml                 # deploy sequence (deploy_solution)
├── solution.yaml               # catalog wrapper: taxonomy, readme, templates
├── agents/
│   ├── customer-management.yaml  # deployable AgentTemplate (parameterized on customer_label)
│   └── customer-management.md     # per-template Library-inspector body
├── diagrams/architecture.svg
├── env.example
└── README.md
```

## Parameterization

The deployable template is parameterized on `customer_label`. That value is
interpolated into the agent's `name` and `identity` when the agent is stamped
for a specific customer, so each customer gets a clearly-named, single-scope
agent. The base (un-stamped) copy shows the `{{customer_label}}` placeholder
literally; supply a `customer_label` at stamp time (or install time) to fill it.

## Validate

```sh
archastro package solution services/agent_network/samples/customer-management
```

## Production catalog publication

The production catalog row is published through the `archagents` sample release
pipeline, not imported from this firstlanding directory at deploy time. Promote
this bundle to the `customer-management` solution sample in `archagents`, bump
that sample's released version in `samples.json`, and let its release workflow
package and deploy the tarball to the catalog before enabling
`agent_customer_management` for external users.

Firstlanding deliberately has no second catalog importer for this bundle. The
onboarding action resolves the released row by the stable lookup key
`customer-management-solution`; keeping one publication owner prevents the
checked-in sample and the installable catalog artifact from drifting silently.
