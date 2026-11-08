# Subnet Allocation for 10.20.0.0/16

## 1. Requirements and Allocation Strategy

We are given the parent block `10.20.0.0/16` (total 65,536 addresses).
Per assignment specifications:
- Subnets are allocated in order of requirement from **largest to smallest**.
- Allocation begins at `10.20.0.0`.
- Each subnet is placed immediately after the previous one with no gaps.
- The smallest prefix length fitting the required number of usable hosts is used.
- Formula for usable hosts: $\text{Usable Hosts} = 2^{32 - \text{prefix}} - 2$.

---

## 2. Step-by-Step Binary Working

### A. Subnet: `app` (Requirement: 1,000 hosts)
- Host bits needed: $2^h - 2 \ge 1000 \implies h = 10$ ($2^{10} - 2 = 1024 - 2 = 1022$).
- Prefix length: $32 - 10 = 22$.
- Network Address: `10.20.0.0/22`
- Subnet Mask: `255.255.252.0`
- IP Block Size: $2^{10} = 1024$ addresses (`10.20.0.0` to `10.20.3.255`).
- Usable Host Range: `10.20.0.1` to `10.20.3.254`
- Broadcast Address: `10.20.3.255`
- Number of Usable Hosts: `1022`

### B. Subnet: `public` (Requirement: 250 hosts)
- Next available address: `10.20.4.0`
- Host bits needed: $2^h - 2 \ge 250 \implies h = 8$ ($2^8 - 2 = 256 - 2 = 254$).
- Prefix length: $32 - 8 = 24$.
- Network Address: `10.20.4.0/24`
- Subnet Mask: `255.255.255.0`
- IP Block Size: $2^8 = 256$ addresses (`10.20.4.0` to `10.20.4.255`).
- Usable Host Range: `10.20.4.1` to `10.20.4.254`
- Broadcast Address: `10.20.4.255`
- Number of Usable Hosts: `254`

### C. Subnet: `data` (Requirement: 100 hosts)
- Next available address: `10.20.5.0`
- Host bits needed: $2^h - 2 \ge 100 \implies h = 7$ ($2^7 - 2 = 128 - 2 = 126$).
- Prefix length: $32 - 7 = 25$.
- Network Address: `10.20.5.0/25`
- Subnet Mask: `255.255.255.128`
- IP Block Size: $2^7 = 128$ addresses (`10.20.5.0` to `10.20.5.127`).
- Usable Host Range: `10.20.5.1` to `10.20.5.126`
- Broadcast Address: `10.20.5.127`
- Number of Usable Hosts: `126`

### D. Subnet: `management` (Requirement: 20 hosts)
- Next available address: `10.20.5.128`
- Host bits needed: $2^h - 2 \ge 20 \implies h = 5$ ($2^5 - 2 = 32 - 2 = 30$).
- Prefix length: $32 - 5 = 27$.
- Network Address: `10.20.5.128/27`
- Subnet Mask: `255.255.255.224`
- IP Block Size: $2^5 = 32$ addresses (`10.20.5.128` to `10.20.5.159`).
- Usable Host Range: `10.20.5.129` to `10.20.5.158`
- Broadcast Address: `10.20.5.159`
- Number of Usable Hosts: `30`

---

## 3. Subnet Allocation Table

| Subnet | Hosts Needed | Network Address | Prefix Length | Usable Host Range | Broadcast Address | Usable Hosts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **app** | 1,000 | `10.20.0.0` | `/22` | `10.20.0.1` – `10.20.3.254` | `10.20.3.255` | 1,022 |
| **public** | 250 | `10.20.4.0` | `/24` | `10.20.4.1` – `10.20.4.254` | `10.20.4.255` | 254 |
| **data** | 100 | `10.20.5.0` | `/25` | `10.20.5.1` – `10.20.5.126` | `10.20.5.127` | 126 |
| **management** | 20 | `10.20.5.128` | `/27` | `10.20.5.129` – `10.20.5.158` | `10.20.5.159` | 30 |

---

## 4. Architectural Reasoning

### Why a Stateless NACL Needs Separate Rules for Reply Traffic
Unlike stateful firewalls (such as Security Groups in AWS) that maintain an internal connection state table and automatically permit return/reply packets of an established TCP session, a **Network Access Control List (NACL) is completely stateless**. 
Each incoming and outgoing packet is inspected in isolation without any memory or tracking of ongoing connections. Therefore:
- When a client establishes an inbound connection on port 80/443, the outbound response sent back to the client's ephemeral port (1024–65535) is treated as a distinct packet and would be blocked unless an explicit outbound allow rule exists.
- Similarly, when the load balancer initiates an outbound request to port 8000 on the `app` subnet, the return packet containing the app's response arrives at the load balancer's ephemeral port (1024–65535) and requires an explicit inbound allow rule.

### Why Rule Order Matters for the `198.51.100.0/24` Abusive Block
NACLs evaluate rules sequentially in ascending numerical order (**lowest rule number first**), and the **first matching rule terminates evaluation** ("first match wins").
- If the block rule for `198.51.100.0/24` were numbered higher than the broad allow rules for port 80/443 (`0.0.0.0/0`), packets originating from `198.51.100.0/24` targeting port 80/443 would match the allow rule first and gain access, completely bypassing the deny rule.
- Placing the deny rule at a lower rule number (Rule 10) guarantees that any packet with a source address in `198.51.100.0/24` is dropped immediately before any general allow rules are considered.
