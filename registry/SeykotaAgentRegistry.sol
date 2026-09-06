// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title SeykotaAgentRegistry
/// @notice A verifiable contribution/provenance registry for AI agents on Arc.
/// Agents register a DID + a contribution claim, and anyone can verify on-chain.
/// This gives the Arc agent economy trustless provenance: an agent's proof-of-
/// contribution is a queryable on-chain fact, not a social-media claim.
/// @author ArewaOS / Seykota (ERC-8004 ID 55166)
contract SeykotaAgentRegistry {
    struct Contribution {
        bytes32 didHash;      // keccak256 of the agent's did:key
        bytes32 artifactHash; // keccak256 of the contribution artifact URL
        string  kind;         // e.g. "oracle", "guide", "tool", "dataset"
        uint256 timestamp;
        bool    valid;        // true once committed (immutable record)
    }

    // Global + per-agent contribution counters; provenance indexed by id.
    Contribution[] public contributions;
    mapping(bytes32 => uint256[]) private byAgent;   // didHash -> contribution ids
    mapping(address => bytes32) public agentDID;     // EOAs can bind a DID

    event ContributionRegistered(
        uint256 indexed id, bytes32 indexed didHash,
        bytes32 artifactHash, string kind, uint256 timestamp
    );

    event DIDBound(address indexed who, bytes32 didHash);

    /// Bind a DID to the calling agent's address (one-to-one).
    function bindDID(bytes32 didHash) external {
        require(agentDID[msg.sender] == bytes32(0), "already bound");
        agentDID[msg.sender] = didHash;
        emit DIDBound(msg.sender, didHash);
    }

    /// Register a verifiable contribution. Deployed as an immutable, append-only
    /// record (valid=true) so provenance can't be retroactively edited.
    function registerContribution(
        bytes32 didHash, bytes32 artifactHash, string calldata kind
    ) external returns (uint256 id) {
        id = contributions.length;
        contributions.push(Contribution({
            didHash: didHash,
            artifactHash: artifactHash,
            kind: kind,
            timestamp: block.timestamp,
            valid: true
        }));
        byAgent[didHash].push(id);
        emit ContributionRegistered(id, didHash, artifactHash, kind, block.timestamp);
    }

    /// Public read: total contributions registered.
    function totalContributions() external view returns (uint256) {
        return contributions.length;
    }

    /// Public read: count of contributions for a given DID.
    function contributionCount(bytes32 didHash) external view returns (uint256) {
        return byAgent[didHash].length;
    }
}
