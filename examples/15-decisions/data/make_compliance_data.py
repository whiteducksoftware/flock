"""Generate the compliance example data: 100 controls and 24 fictional documents.

The controls are written for these examples, loosely modelled on the topics of
common security frameworks (ISO/IEC 27001, NIS2, BSI IT-Grundschutz); they are
not quotes from any of them. The documents are built from statements about the
controls, so every document comes with ground truth:

- a control is ``yes`` when the document contains a statement that it is
  implemented,
- ``no`` when the document states a gap or does not mention the control.

Every statement is also kept as an evidence sentence with its control, for
mapping evidence to controls.

Run: ``uv run examples/15-decisions/data/make_compliance_data.py``
"""

from __future__ import annotations

import json
import random
from pathlib import Path


HERE = Path(__file__).parent

# id, requirement, two statements that show the control is implemented, one gap statement
CONTROLS: dict[str, list[tuple[str, str, tuple[str, str], str]]] = {
    "Governance": [
        (
            "gov_01",
            "An information security policy is approved by management and published to all staff",
            (
                "This policy was approved by the executive board and is published on the intranet for all employees.",
                "Management signed off the information security policy, and every staff member can read it in the policy portal.",
            ),
            "A company-wide information security policy has been drafted but not yet approved by management.",
        ),
        (
            "gov_02",
            "The security policies are reviewed at least once a year",
            (
                "All security policies are reviewed annually and after major organisational changes.",
                "The CISO reviews this document every twelve months; the last review was completed in March.",
            ),
            "The policies have not been reviewed since they were first issued four years ago.",
        ),
        (
            "gov_03",
            "Security roles and responsibilities, including a CISO, are assigned",
            (
                "A Chief Information Security Officer is appointed and reports directly to the managing director.",
                "Responsibilities for information security are assigned to named roles, led by the CISO.",
            ),
            "There is currently no designated person responsible for information security.",
        ),
        (
            "gov_04",
            "Conflicting duties are segregated",
            (
                "Requesting, approving and implementing a change are performed by different people.",
                "Payments above 10,000 EUR require approval by a second person who did not initiate them.",
            ),
            "Due to the small team, administrators approve and implement their own changes.",
        ),
        (
            "gov_05",
            "Management receives regular reports on the security status",
            (
                "The CISO presents a security status report to the board every quarter.",
                "Key security metrics are reported to management in a monthly dashboard.",
            ),
            "Security topics are only discussed with management when an incident occurs.",
        ),
        (
            "gov_06",
            "Contacts with authorities and the responsible CSIRT are defined",
            (
                "Contact details of the national CSIRT and the supervisory authority are maintained in the crisis handbook.",
                "The company has registered with the responsible authority and keeps an up-to-date contact list for reporting.",
            ),
            "It has not yet been determined which authority must be contacted in a security emergency.",
        ),
        (
            "gov_07",
            "Information security is part of project management",
            (
                "Every project passes a security checkpoint before go-live.",
                "Project charters include a security assessment that the CISO signs off.",
            ),
            "Projects are planned and delivered without a defined security review.",
        ),
        (
            "gov_08",
            "Legal, regulatory and contractual security requirements are identified in a register",
            (
                "A compliance register lists all legal and contractual security obligations, including NIS2.",
                "Legal requirements relevant to information security are tracked in a register maintained by the legal department.",
            ),
            "Applicable legal and regulatory security requirements have not been systematically identified.",
        ),
    ],
    "Risk management": [
        (
            "risk_01",
            "A documented risk assessment methodology is defined",
            (
                "Risks are assessed using a documented methodology that rates likelihood and impact on a five-point scale.",
                "The risk management standard defines how threats, vulnerabilities and impact are assessed.",
            ),
            "Risks are assessed informally; no common method is defined.",
        ),
        (
            "risk_02",
            "Information security risk assessments are performed at least annually",
            (
                "A full information security risk assessment is carried out every year.",
                "The annual risk assessment was completed in Q2 and covered all critical business processes.",
            ),
            "The last risk assessment dates back three years.",
        ),
        (
            "risk_03",
            "A risk treatment plan with owners and deadlines exists",
            (
                "Each identified risk has a treatment plan with an owner and a due date.",
                "Risk treatment measures are tracked with responsible owners and target dates.",
            ),
            "Identified risks are documented, but no treatment measures or owners have been assigned.",
        ),
        (
            "risk_04",
            "Residual risks are formally accepted by management",
            (
                "Residual risks above the risk appetite are formally accepted by the board.",
                "Risk owners from senior management sign the acceptance of remaining risks.",
            ),
            "It is unclear who may accept residual risks.",
        ),
        (
            "risk_05",
            "A risk register is maintained",
            (
                "All information security risks are recorded in a central risk register.",
                "The risk register is updated whenever new risks are identified.",
            ),
            "Risks are not recorded in a central place.",
        ),
        (
            "risk_06",
            "Threat intelligence is collected and used",
            (
                "The security team subscribes to threat intelligence feeds and evaluates relevant warnings weekly.",
                "Advisories from the national CERT are monitored and assessed for their relevance.",
            ),
            "Information about current threats is not collected systematically.",
        ),
    ],
    "Asset management": [
        (
            "asset_01",
            "An inventory of information assets is maintained",
            (
                "An inventory of all hardware, software and information assets is kept in the CMDB.",
                "All servers, laptops and business applications are listed in a maintained asset inventory.",
            ),
            "There is no complete overview of the IT systems in use.",
        ),
        (
            "asset_02",
            "Every asset has an owner",
            (
                "Each asset in the inventory has a named owner.",
                "Owners are assigned to every application and data set.",
            ),
            "Ownership of many systems is unclear.",
        ),
        (
            "asset_03",
            "Rules for the acceptable use of IT resources are defined",
            (
                "An acceptable use policy defines how company devices and accounts may be used.",
                "Employees acknowledge the rules for acceptable use of IT resources when they join.",
            ),
            "No rules for the private use of company devices have been defined.",
        ),
        (
            "asset_04",
            "Assets are returned when employment ends",
            (
                "Leavers return laptops, phones and access badges on their last working day, documented in a checklist.",
                "HR confirms the return of all company equipment before the final salary payment.",
            ),
            "Equipment of former employees is not always collected.",
        ),
        (
            "asset_05",
            "Information is classified by protection need",
            (
                "Information is classified as public, internal, confidential or strictly confidential.",
                "A classification scheme with four levels defines the protection need of information.",
            ),
            "Information is not classified according to its protection need.",
        ),
        (
            "asset_06",
            "Classified information is labelled",
            (
                "Confidential documents carry a classification label in the header.",
                "Email and document templates apply the classification label automatically.",
            ),
            "Documents are not labelled with their classification.",
        ),
    ],
    "Access control": [
        (
            "acc_01",
            "An access control policy is defined",
            (
                "An access control policy defines how access to systems is requested, granted and removed.",
                "Rules for granting and withdrawing access are laid down in the access control policy.",
            ),
            "Access is granted on request without a defined policy.",
        ),
        (
            "acc_02",
            "Users have unique accounts; shared accounts are not used",
            (
                "Every user has a personal account; shared accounts are prohibited.",
                "Group logins have been replaced by personal accounts for all staff.",
            ),
            "Several teams still share one login for the warehouse system.",
        ),
        (
            "acc_03",
            "Multi-factor authentication is required for remote and privileged access",
            (
                "Remote access and all administrator logins require multi-factor authentication.",
                "MFA with an authenticator app is mandatory for VPN and privileged accounts.",
            ),
            "Multi-factor authentication is planned but not yet enforced for remote access.",
        ),
        (
            "acc_04",
            "Access rights are reviewed periodically",
            (
                "System owners review all access rights every quarter.",
                "An annual recertification of user permissions is carried out by the line managers.",
            ),
            "Access rights have never been reviewed after they were granted.",
        ),
        (
            "acc_05",
            "Access of leavers is revoked promptly",
            (
                "Accounts of leavers are disabled within 24 hours of their departure.",
                "HR triggers the deactivation of all accounts on the last working day.",
            ),
            "Accounts of former employees are sometimes active for weeks after they leave.",
        ),
        (
            "acc_06",
            "Privileged accounts are separate and restricted",
            (
                "Administrators use separate privileged accounts that are not used for email or browsing.",
                "Privileged access is limited to a small group and managed in a privileged access management tool.",
            ),
            "Administrators work with their normal accounts, which have domain admin rights.",
        ),
        (
            "acc_07",
            "Password rules require strong passwords",
            (
                "Passwords must have at least 14 characters and are checked against lists of breached passwords.",
                "The password policy requires long passphrases and blocks commonly used passwords.",
            ),
            "There are no requirements for password length or complexity.",
        ),
        (
            "acc_08",
            "Access follows least privilege and need-to-know",
            (
                "Users receive only the permissions they need for their tasks.",
                "Access is granted on a need-to-know basis and limited to the minimum required.",
            ),
            "New employees receive the same broad permissions as their colleagues by default.",
        ),
        (
            "acc_09",
            "Granting and changing access is approved",
            (
                "New access and changes of permissions are approved by the line manager in the ticket system.",
                "Joiner and mover requests require documented approval before accounts are created or changed.",
            ),
            "Accounts are created on informal request without approval.",
        ),
        (
            "acc_10",
            "Sessions are locked after inactivity",
            (
                "Workstations lock automatically after 10 minutes of inactivity.",
                "Sessions in business applications end after 15 minutes without activity.",
            ),
            "Screens remain unlocked when users leave their desks.",
        ),
        (
            "acc_11",
            "Service accounts are inventoried and have owners",
            (
                "All technical service accounts are listed with an owner and purpose.",
                "Service accounts are inventoried and their passwords are rotated regularly.",
            ),
            "Nobody knows how many technical accounts exist or what they are used for.",
        ),
        (
            "acc_12",
            "Emergency access is controlled and logged",
            (
                "Break-glass accounts are sealed, and every use is logged and reviewed.",
                "Emergency access credentials are kept in a safe and their use triggers an alert.",
            ),
            "Emergency access is possible via a shared administrator password without logging.",
        ),
    ],
    "Cryptography": [
        (
            "cry_01",
            "Sensitive data is encrypted at rest",
            (
                "Databases and backups with personal data are encrypted at rest.",
                "All laptops use full-disk encryption, and file shares with confidential data are encrypted.",
            ),
            "Customer data on the file server is stored unencrypted.",
        ),
        (
            "cry_02",
            "Data in transit is encrypted with current protocols",
            (
                "All external connections use TLS 1.2 or higher.",
                "Data is only transmitted over encrypted channels; outdated protocols are disabled.",
            ),
            "Some internal interfaces still transfer data over unencrypted FTP.",
        ),
        (
            "cry_03",
            "Cryptographic keys are managed over their lifecycle",
            (
                "Keys are generated, stored, rotated and destroyed according to the key management standard.",
                "Cryptographic keys are stored in a hardware security module and rotated yearly.",
            ),
            "Encryption keys are stored in configuration files without a defined rotation.",
        ),
        (
            "cry_04",
            "Certificates are inventoried and renewed in time",
            (
                "All certificates are tracked in an inventory with automated expiry alerts.",
                "Certificates are renewed automatically 30 days before they expire.",
            ),
            "Certificates have expired unnoticed several times in the past year.",
        ),
        (
            "cry_05",
            "Approved cryptographic algorithms are defined",
            (
                "A list of approved algorithms and key lengths is maintained in the cryptography standard.",
                "Only algorithms approved in the cryptography concept may be used.",
            ),
            "Developers choose encryption algorithms on their own.",
        ),
    ],
    "Physical security": [
        (
            "phy_01",
            "The premises have a physical perimeter with badge access",
            (
                "Office areas can only be entered with a personal access badge.",
                "The building is protected by a fenced perimeter and badge-controlled doors.",
            ),
            "The office entrance is open during business hours without access control.",
        ),
        (
            "phy_02",
            "Visitors are registered and accompanied",
            (
                "Visitors sign in at reception and are accompanied by an employee at all times.",
                "All visitors are registered and receive a visitor badge.",
            ),
            "Visitors can move around the building without being registered.",
        ),
        (
            "phy_03",
            "Access to the data centre is restricted and logged",
            (
                "Access to the server room is restricted to authorised IT staff and logged electronically.",
                "Every entry to the data centre is recorded and reviewed monthly.",
            ),
            "The server room key is kept in an unlocked drawer at reception.",
        ),
        (
            "phy_04",
            "IT rooms are protected against fire and power failure",
            (
                "The server room has fire detection, a gas extinguishing system and an uninterruptible power supply.",
                "A UPS and an emergency generator protect the data centre against power outages.",
            ),
            "The server room has no fire detection.",
        ),
        (
            "phy_05",
            "Clear desk and clear screen rules apply",
            (
                "A clear desk rule requires confidential documents to be locked away.",
                "Employees must lock their screens and clear their desks when leaving the workplace.",
            ),
            "Confidential printouts are regularly left on desks overnight.",
        ),
        (
            "phy_06",
            "Storage media are disposed of securely",
            (
                "Hard drives are physically destroyed by a certified disposal company.",
                "Data carriers are securely wiped or shredded before disposal.",
            ),
            "Old hard drives are disposed of with normal electronic waste.",
        ),
    ],
    "Operations": [
        (
            "ops_01",
            "Operating procedures are documented",
            (
                "Operating procedures for all critical systems are documented in the operations handbook.",
                "Standard operating procedures describe start-up, shutdown and maintenance of the systems.",
            ),
            "Knowledge about operating the systems exists only in the heads of two administrators.",
        ),
        (
            "ops_02",
            "Changes follow a change management process with approval",
            (
                "Changes to production systems require an approved change request.",
                "A change advisory board approves all significant changes before implementation.",
            ),
            "Changes are made directly in production without a formal process.",
        ),
        (
            "ops_03",
            "Capacity is monitored and planned",
            (
                "Storage, CPU and network capacity are monitored and forecast quarterly.",
                "Capacity thresholds trigger alerts and are reviewed in monthly operations meetings.",
            ),
            "Capacity bottlenecks are only noticed when systems slow down.",
        ),
        (
            "ops_04",
            "Development, test and production environments are separated",
            (
                "Development, test and production run in separate environments with separate access.",
                "Production is isolated from test systems; developers have no write access to production.",
            ),
            "Developers test new versions directly on the production system.",
        ),
        (
            "ops_05",
            "Endpoints are protected against malware",
            (
                "All endpoints run an endpoint detection and response agent that is centrally managed.",
                "Malware protection is installed on every server and laptop and updated automatically.",
            ),
            "Malware protection is missing on several servers.",
        ),
        (
            "ops_06",
            "Security events are logged centrally",
            (
                "Security-relevant events from servers, firewalls and applications are collected in a central SIEM.",
                "Log data of all critical systems is forwarded to a central log management platform.",
            ),
            "Logs are only stored locally on each system.",
        ),
        (
            "ops_07",
            "Log retention periods are defined",
            (
                "Security logs are retained for twelve months.",
                "Retention periods for log data are defined per log type, at least 180 days.",
            ),
            "No retention period is defined for log data.",
        ),
        (
            "ops_08",
            "Logs are protected against tampering",
            (
                "Log data is stored write-once and administrators cannot delete it.",
                "Integrity of the log archive is protected by hashing and restricted access.",
            ),
            "Administrators can modify or delete the logs of their own systems.",
        ),
        (
            "ops_09",
            "System clocks are synchronised",
            (
                "All systems synchronise their clocks with a central NTP service.",
                "Time synchronisation via NTP ensures consistent timestamps across systems.",
            ),
            "Clocks of several systems deviate by several minutes.",
        ),
        (
            "ops_10",
            "Security events are monitored around the clock",
            (
                "A security operations centre monitors alerts 24/7.",
                "Security alerts are handled around the clock by an external managed SOC.",
            ),
            "Security alerts are only reviewed during business hours.",
        ),
        (
            "ops_11",
            "Systems are hardened according to configuration baselines",
            (
                "Servers are configured according to hardening baselines based on CIS benchmarks.",
                "Secure configuration baselines are defined and checked automatically.",
            ),
            "Systems are operated with their default configuration.",
        ),
        (
            "ops_12",
            "Installing software is restricted",
            (
                "Users cannot install software; installations are made through the software centre.",
                "Only approved software from an allowlist can be installed on workstations.",
            ),
            "Every user can install any software on their laptop.",
        ),
    ],
    "Vulnerability management": [
        (
            "vul_01",
            "Systems are scanned for vulnerabilities regularly",
            (
                "All internal and external systems are scanned for vulnerabilities weekly.",
                "Vulnerability scans cover the entire network every month.",
            ),
            "Vulnerability scans are not performed.",
        ),
        (
            "vul_02",
            "Critical security patches are applied within a defined time",
            (
                "Critical patches are installed within 7 days of release.",
                "Security updates rated critical must be applied within one week.",
            ),
            "Patches are installed irregularly, sometimes months after release.",
        ),
        (
            "vul_03",
            "Penetration tests are performed at least annually",
            (
                "An external penetration test of the internet-facing systems is performed every year.",
                "Independent testers carry out an annual penetration test.",
            ),
            "No penetration test has been performed so far.",
        ),
        (
            "vul_04",
            "Vulnerabilities are tracked until closure",
            (
                "Found vulnerabilities are tracked in tickets until they are fixed and verified.",
                "Each finding is assigned an owner and a deadline and followed up until closure.",
            ),
            "Scan results are not followed up.",
        ),
        (
            "vul_05",
            "End-of-life software is identified and replaced",
            (
                "Software and systems without vendor support are identified and replaced on schedule.",
                "A lifecycle plan ensures that no unsupported operating systems remain in use.",
            ),
            "Several servers still run an operating system that no longer receives updates.",
        ),
        (
            "vul_06",
            "External vulnerability reports can be submitted and are handled",
            (
                "A published security contact and disclosure policy allow researchers to report vulnerabilities.",
                "Reports of vulnerabilities from external parties are handled through a defined process.",
            ),
            "There is no way for outsiders to report vulnerabilities.",
        ),
    ],
    "Network security": [
        (
            "net_01",
            "The network is segmented",
            (
                "The network is divided into segments for office, production and administration.",
                "Production systems are separated from the office network by firewalls.",
            ),
            "All systems are in one flat network.",
        ),
        (
            "net_02",
            "Firewall rules are reviewed regularly",
            (
                "Firewall rules are reviewed every six months and unused rules are removed.",
                "A semi-annual firewall rule review is documented by the network team.",
            ),
            "Firewall rules have accumulated over years without review.",
        ),
        (
            "net_03",
            "Remote access is only possible through a secured VPN",
            (
                "Remote access to internal systems is only possible through the company VPN.",
                "External access to the network requires a VPN connection.",
            ),
            "Remote desktop is reachable directly from the internet.",
        ),
        (
            "net_04",
            "Wireless networks are secured and guests are separated",
            (
                "The corporate Wi-Fi uses WPA3-Enterprise; guests use a separate network.",
                "Guest Wi-Fi is isolated from the internal network.",
            ),
            "Guests use the same Wi-Fi as employees.",
        ),
        (
            "net_05",
            "Internet-facing services are protected against DDoS",
            (
                "A DDoS protection service filters traffic to the web shop.",
                "Internet-facing services are protected by the provider's DDoS mitigation.",
            ),
            "There is no protection against denial-of-service attacks.",
        ),
        (
            "net_06",
            "Web and DNS traffic is filtered",
            (
                "A secure web gateway blocks known malicious websites.",
                "DNS filtering prevents access to malicious domains.",
            ),
            "Internet traffic is not filtered.",
        ),
        (
            "net_07",
            "A current network plan exists",
            (
                "A current network diagram documents all segments and interfaces.",
                "The network plan is updated with every change to the infrastructure.",
            ),
            "The network documentation is outdated.",
        ),
    ],
    "Secure development": [
        (
            "dev_01",
            "A secure development lifecycle is defined",
            (
                "Software is developed according to a secure development lifecycle with security activities in every phase.",
                "The development process defines security requirements, reviews and tests for each release.",
            ),
            "Security is not part of the development process.",
        ),
        (
            "dev_02",
            "Secure coding guidelines are defined",
            (
                "Developers follow secure coding guidelines based on the OWASP Top 10.",
                "Secure coding standards are defined for every programming language in use.",
            ),
            "There are no secure coding guidelines.",
        ),
        (
            "dev_03",
            "Code is reviewed before it is merged",
            (
                "Every change is reviewed by a second developer before it is merged.",
                "Pull requests require at least one approving review.",
            ),
            "Developers merge their own changes without review.",
        ),
        (
            "dev_04",
            "Security tests run in the build pipeline",
            (
                "Static and dynamic security tests run automatically in the CI pipeline.",
                "The build pipeline includes SAST and DAST scans that block critical findings.",
            ),
            "Security testing is done manually, if at all.",
        ),
        (
            "dev_05",
            "Third-party dependencies are scanned",
            (
                "Third-party libraries are scanned for known vulnerabilities, and an SBOM is produced for each release.",
                "Dependency scanning alerts the team about vulnerable open-source components.",
            ),
            "Nobody tracks which open-source libraries are used.",
        ),
        (
            "dev_06",
            "Secrets are not stored in source code",
            (
                "Secrets are stored in a vault; secret scanning prevents them from being committed.",
                "Passwords and API keys are injected at runtime and never stored in the repository.",
            ),
            "API keys are stored in the source code repository.",
        ),
        (
            "dev_07",
            "Test data contains no production personal data",
            (
                "Test environments use synthetic or anonymised data only.",
                "Production personal data must not be copied into test systems.",
            ),
            "Copies of the production database are used for testing.",
        ),
    ],
    "Suppliers": [
        (
            "sup_01",
            "Suppliers are assessed for security before onboarding",
            (
                "New suppliers with access to company data undergo a security assessment before the contract is signed.",
                "A security questionnaire and evidence review are mandatory for new IT service providers.",
            ),
            "Suppliers are selected without a security assessment.",
        ),
        (
            "sup_02",
            "Security requirements are part of supplier contracts",
            (
                "Contracts with suppliers contain security and confidentiality clauses and audit rights.",
                "Supplier agreements define security obligations and incident notification duties.",
            ),
            "Supplier contracts do not contain security requirements.",
        ),
        (
            "sup_03",
            "Suppliers are reviewed periodically",
            (
                "Critical suppliers are reviewed annually against their security obligations.",
                "The security performance of key suppliers is evaluated every year.",
            ),
            "Suppliers are not reviewed after onboarding.",
        ),
        (
            "sup_04",
            "Cloud services are assessed before use",
            (
                "Cloud services are only used after a security assessment, including data location and certifications.",
                "Every new cloud service is approved by the CISO before use.",
            ),
            "Departments subscribe to cloud services without involving IT security.",
        ),
        (
            "sup_05",
            "Supplier access is restricted and time-limited",
            (
                "Supplier access is granted only for the duration of the assignment and is monitored.",
                "Remote maintenance access for suppliers is activated on demand and logged.",
            ),
            "Suppliers have permanent, unmonitored remote access.",
        ),
        (
            "sup_06",
            "Supply chain security risks are considered",
            (
                "Security risks in the ICT supply chain, including the suppliers of our suppliers, are assessed.",
                "Supply chain risks are part of the annual risk assessment, as required by NIS2.",
            ),
            "Risks from the supply chain are not considered.",
        ),
    ],
    "Incident management": [
        (
            "inc_01",
            "An incident response plan exists",
            (
                "An incident response plan defines roles, escalation paths and communication.",
                "The incident response plan describes how security incidents are detected, contained and resolved.",
            ),
            "There is no documented plan for handling security incidents.",
        ),
        (
            "inc_02",
            "Incidents are reported internally within a defined time",
            (
                "Employees must report suspected security incidents to the service desk immediately, at the latest within one hour.",
                "Security incidents are reported to the CISO within one hour of detection.",
            ),
            "There is no defined reporting channel for security incidents.",
        ),
        (
            "inc_03",
            "Significant incidents are reported to the authority within 24 hours",
            (
                "Significant incidents are reported to the national authority with an early warning within 24 hours.",
                "The reporting duty under NIS2 is met: an early warning within 24 hours and a full report within 72 hours.",
            ),
            "Reporting obligations towards the authorities are not known to the incident team.",
        ),
        (
            "inc_04",
            "Incidents are classified by severity",
            (
                "Incidents are classified into four severity levels that determine response times.",
                "A severity matrix defines how incidents are prioritised.",
            ),
            "All incidents are handled in the order they come in.",
        ),
        (
            "inc_05",
            "Lessons learned are captured after incidents",
            (
                "After every major incident, a post-incident review documents lessons learned.",
                "Findings from incidents are tracked as improvement measures.",
            ),
            "Incidents are closed without analysing their causes.",
        ),
        (
            "inc_06",
            "Evidence is collected and preserved",
            (
                "Forensic evidence is collected and preserved according to a documented procedure.",
                "Logs and disk images relevant to an incident are secured with a chain of custody.",
            ),
            "Affected systems are reinstalled immediately without securing evidence.",
        ),
        (
            "inc_07",
            "Incident response is exercised",
            (
                "The incident response team runs a tabletop exercise twice a year.",
                "Incident response procedures are tested annually in a simulated attack.",
            ),
            "The incident response plan has never been tested.",
        ),
    ],
    "Business continuity": [
        (
            "bcm_01",
            "A business impact analysis has been performed",
            (
                "A business impact analysis determined the maximum tolerable downtime of all critical processes.",
                "Recovery time objectives were derived from a business impact analysis.",
            ),
            "It is not known how long critical processes can be interrupted.",
        ),
        (
            "bcm_02",
            "A business continuity plan exists",
            (
                "A business continuity plan describes how critical processes continue during a crisis.",
                "Emergency and recovery plans exist for all critical business processes.",
            ),
            "There is no business continuity plan.",
        ),
        (
            "bcm_03",
            "Continuity plans are exercised at least annually",
            (
                "The business continuity plan is exercised every year, most recently with a data centre failover.",
                "An annual continuity exercise tests the recovery of critical services.",
            ),
            "The continuity plan has never been exercised.",
        ),
        (
            "bcm_04",
            "Backups are performed regularly",
            (
                "All business data is backed up daily.",
                "Incremental backups run every night and full backups every week.",
            ),
            "Backups are performed irregularly and only for some systems.",
        ),
        (
            "bcm_05",
            "Backups are encrypted and stored offline or off-site",
            (
                "Backups are encrypted and stored in a second location, with an offline copy.",
                "An immutable, offline copy of all backups protects against ransomware.",
            ),
            "Backups are stored on a share in the same network as the production systems.",
        ),
        (
            "bcm_06",
            "Restores from backup are tested",
            (
                "Restores from backup are tested every quarter.",
                "A full restore test of the ERP system is performed twice a year.",
            ),
            "Restoring from backup has never been tested.",
        ),
    ],
    "People": [
        (
            "hr_01",
            "Background checks are performed before hiring",
            (
                "Candidates for sensitive positions undergo background checks before hiring.",
                "References and certificates of good conduct are checked before employment starts.",
            ),
            "No background checks are performed.",
        ),
        (
            "hr_02",
            "Employees sign confidentiality agreements",
            (
                "All employees and contractors sign a confidentiality agreement.",
                "Confidentiality obligations are part of every employment contract.",
            ),
            "Contractors are not bound by confidentiality agreements.",
        ),
        (
            "hr_03",
            "Security awareness training is held regularly",
            (
                "All employees complete security awareness training when they join and every year.",
                "Annual security awareness training is mandatory for all staff.",
            ),
            "Employees receive no security awareness training.",
        ),
        (
            "hr_04",
            "Phishing simulations are carried out",
            (
                "Phishing simulations are run every quarter, followed by targeted training.",
                "Regular simulated phishing campaigns measure and improve employee awareness.",
            ),
            "Employees have never been tested with simulated phishing.",
        ),
        (
            "hr_05",
            "A disciplinary process for security violations exists",
            (
                "Violations of security policies are handled in a defined disciplinary process.",
                "Security breaches by employees lead to measures according to the disciplinary procedure.",
            ),
            "Violations of security rules have no consequences.",
        ),
        (
            "hr_06",
            "Security duties continue after termination",
            (
                "Confidentiality obligations remain in force after the end of employment.",
                "Leavers are reminded of their ongoing confidentiality obligations in the exit interview.",
            ),
            "Obligations after termination are not addressed.",
        ),
    ],
}

FILLER = [
    "This document applies to all employees, contractors and temporary staff.",
    "Exceptions must be documented and approved.",
    "Questions about this document can be addressed to the information security team.",
    "The requirements apply to all locations and subsidiaries.",
    "Compliance with this document is checked during internal audits.",
]

ORGS = [
    "Brightwater Logistics",
    "Kestrel Health Services",
    "Alder Grid Energy",
    "Northcove Insurance",
    "Mistral Water Works",
    "Quillon Software",
    "Harbourline Shipping",
    "Ostara Foods",
    "Pellucid Payments",
    "Tamsin Hospitals",
    "Verdant Rail",
    "Lumen Telecom",
]

DOCUMENTS = [
    ("Information Security Policy", ["Governance", "Risk management", "People"]),
    ("Access Management Procedure", ["Access control"]),
    ("Incident Response Plan", ["Incident management"]),
    ("Backup and Recovery Concept", ["Business continuity"]),
    ("Supplier Security Standard", ["Suppliers"]),
    (
        "Secure Development Guideline",
        ["Secure development", "Vulnerability management"],
    ),
    ("Network Security Concept", ["Network security", "Cryptography"]),
    ("Operations Handbook (security excerpt)", ["Operations"]),
    ("Physical Security Standard", ["Physical security", "Asset management"]),
    (
        "Internal Audit Report: ISMS",
        ["Governance", "Risk management", "Asset management", "Access control"],
    ),
    (
        "NIS2 Readiness Assessment",
        ["Incident management", "Suppliers", "Business continuity", "Cryptography"],
    ),
    (
        "IT Security Concept",
        ["Operations", "Vulnerability management", "Network security"],
    ),
]

# Share of controls in a document's domains: implemented, stated as a gap, not mentioned
YES, GAP = 0.65, 0.15


def section_text(rng: random.Random, controls, labels, evidence) -> str:
    sentences = []
    for cid, _text, yes, gap in controls:
        roll = rng.random()
        if roll < YES:
            sentence = rng.choice(yes)
            labels[cid] = "yes"
            evidence.append({"text": sentence, "control": cid})
        elif roll < YES + GAP:
            sentence = gap
        else:
            continue
        sentences.append(sentence)
    rng.shuffle(sentences)
    if rng.random() < 0.5:
        sentences.insert(rng.randrange(len(sentences) + 1), rng.choice(FILLER))
    return " ".join(sentences)


def build_documents(rng: random.Random) -> list[dict]:
    documents = []
    for index in range(24):
        title, domains = DOCUMENTS[index % len(DOCUMENTS)]
        org = (
            ORGS[index % len(ORGS)]
            if index < len(ORGS)
            else ORGS[(index * 5 + 3) % len(ORGS)]
        )
        version = f"{rng.randint(1, 4)}.{rng.randint(0, 9)}"
        labels = {cid: "no" for items in CONTROLS.values() for cid, *_ in items}
        evidence: list[dict] = []
        parts = [
            f"{title}",
            f"{org} · version {version}",
            f"Purpose: This document describes how {org} protects its information and systems.",
        ]
        for number, domain in enumerate(domains, start=1):
            body = section_text(rng, CONTROLS[domain], labels, evidence)
            if body:
                parts.append(f"{number}. {domain}\n{body}")
        documents.append({
            "id": f"doc_{index + 1:02d}",
            "title": title,
            "organisation": org,
            "text": "\n\n".join(parts),
            "labels": labels,
            "evidence": evidence,
        })
    return documents


def main() -> None:
    controls = [
        {"id": cid, "domain": domain, "text": text}
        for domain, items in CONTROLS.items()
        for cid, text, _yes, _gap in items
    ]
    assert len(controls) == 100, len(controls)
    documents = build_documents(random.Random(466))
    (HERE / "compliance_controls.json").write_text(
        json.dumps(controls, indent=1, ensure_ascii=False) + "\n"
    )
    (HERE / "compliance_documents.json").write_text(
        json.dumps(documents, indent=1, ensure_ascii=False) + "\n"
    )
    implemented = sum(v == "yes" for d in documents for v in d["labels"].values())
    print(
        f"{len(controls)} controls, {len(documents)} documents, "
        f"{implemented} implemented controls, "
        f"{sum(len(d['evidence']) for d in documents)} evidence sentences"
    )


if __name__ == "__main__":
    main()
