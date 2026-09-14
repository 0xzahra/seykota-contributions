// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/*
  AgentLaunchpad — a launchpad for AI agents on Arc (Circle L1, chain 5042002).

  What it does:
    1. AGENTS register a verifiable identity (keccak256(did:key) + name + metadata URI).
    2. Each agent LAUNCHES its own token (a minimal ERC-20 minted by this factory).
    3. The launched token trades on a per-token LINEAR BONDING CURVE, quoted in an
       ERC-20 quote asset (test lUSD here; Arc's canonical USDC on mainnet).
       price(n) = basePrice + slope * n   (n = whole tokens already sold on the curve)

  Provenance design: a launch is permanently tied to the creator address AND the
  creator's DID hash, so "who launched this token" is a queryable on-chain fact,
  not a social claim. The token, the curve, and the identity live in one record.

  Author: ArewaOS / Seykota (ERC-8004 ID 55166) — built for the Arc agent economy.
*/

/* ------------------------------ minimal ERC-20 ------------------------------ */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
    function decimals() external view returns (uint8);
}

/// @notice Test quote asset for the launchpad curve (6 decimals). Faucet-able.
contract LaunchUSD {
    string public constant name = "Launch USD (test)";
    string public constant symbol = "lUSD";
    uint8 public constant decimals = 6;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    /// Public faucet so anyone can grab test liquidity (testnet only).
    function faucet(uint256 amount) external {
        totalSupply += amount;
        balanceOf[msg.sender] += amount;
        emit Transfer(address(0), msg.sender, amount);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        return _move(msg.sender, to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "lUSD: allowance");
        if (a != type(uint256).max) {
            allowance[from][msg.sender] = a - amount;
        }
        return _move(from, to, amount);
    }

    function _move(address from, address to, uint256 amount) internal returns (bool) {
        require(balanceOf[from] >= amount, "lUSD: balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}

/// @notice Minimal ERC-20 launched by the pad. Only the pad (minter) may mint/burn.
contract AgentToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;

    address public immutable minter;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor(string memory _name, string memory _symbol, address _minter) {
        name = _name;
        symbol = _symbol;
        minter = _minter;
    }

    modifier onlyMinter() {
        require(msg.sender == minter, "AgentToken: only pad");
        _;
    }

    function mint(address to, uint256 amount) external onlyMinter {
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function burn(address from, uint256 amount) external onlyMinter {
        require(balanceOf[from] >= amount, "AgentToken: burn > bal");
        balanceOf[from] -= amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        return _move(msg.sender, to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "AgentToken: allowance");
        if (a != type(uint256).max) {
            allowance[from][msg.sender] = a - amount;
        }
        return _move(from, to, amount);
    }

    function _move(address from, address to, uint256 amount) internal returns (bool) {
        require(balanceOf[from] >= amount, "AgentToken: balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}

/* ------------------------------- the launchpad ------------------------------ */

contract AgentLaunchpad {
    uint256 private constant ONE_TOKEN = 1e18; // curve accounting is in whole tokens

    struct Agent {
        bytes32 didHash;      // keccak256 of the agent's did:key
        string  name;
        string  metadataURI;  // ipfs:// or https:// pointer to the agent card
        uint256 launched;     // how many tokens this agent has launched
        uint256 registeredAt;
        bool    exists;
    }

    struct Launch {
        uint256 id;
        address token;
        address creator;
        bytes32 didHash;
        string  name;
        string  symbol;
        uint256 totalSupply;   // whole tokens, hard cap
        uint256 curveSupply;   // whole tokens sold on the curve
        uint256 sold;          // whole tokens sold so far
        uint256 reserve;       // quote held to buy back curve tokens
        uint256 basePrice;     // quote-units per whole token at sold == 0
        uint256 slope;         // quote-units added to price per whole token sold
        uint256 raised;        // cumulative quote taken in on buys
        bool    graduated;     // curve fully sold
        uint256 createdAt;
    }

    IERC20  public immutable quote;
    address public owner;
    uint256 public buyFeeBps;   // protocol fee on buys, to owner
    uint256 public sellFeeBps;  // protocol fee on sells, to owner

    mapping(address => Agent) private _agents;
    address[] private _agentList;

    Launch[] private _launches;
    mapping(address => uint256) public launchOfToken;             // token -> launch id + 1
    mapping(address => uint256[]) private _agentLaunchIds;        // agent -> launch ids

    event AgentRegistered(address indexed agent, bytes32 indexed didHash, string name, string metadataURI);
    event TokenLaunched(
        uint256 indexed id, address indexed token, address indexed creator,
        bytes32 didHash, string symbol, uint256 totalSupply, uint256 curveSupply
    );
    event Bought(uint256 indexed id, address indexed buyer, uint256 wholeTokens, uint256 cost, uint256 fee);
    event Sold(uint256 indexed id, address indexed seller, uint256 wholeTokens, uint256 refund, uint256 fee);
    event Graduated(uint256 indexed id, uint256 raised);
    event FeesSet(uint256 buyFeeBps, uint256 sellFeeBps);

    constructor(address quoteToken) {
        require(quoteToken != address(0), "quote=0");
        quote = IERC20(quoteToken);
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    /* ------------------------------- registry ------------------------------- */

    /// @notice Register the calling agent. One identity per address, immutable once set.
    function registerAgent(bytes32 didHash, string calldata name, string calldata metadataURI) external {
        require(!_agents[msg.sender].exists, "already registered");
        require(didHash != bytes32(0), "didHash=0");
        require(bytes(name).length > 0, "name required");
        _agents[msg.sender] = Agent({
            didHash: didHash,
            name: name,
            metadataURI: metadataURI,
            launched: 0,
            registeredAt: block.timestamp,
            exists: true
        });
        _agentList.push(msg.sender);
        emit AgentRegistered(msg.sender, didHash, name, metadataURI);
    }

    /* ------------------------------- launching ------------------------------ */

    /// @notice Launch a token on the curve. Caller must be a registered agent.
    /// @param totalSupply  whole-token hard cap (curveSupply is part of it)
    /// @param curveSupply  whole tokens offered on the bonding curve
    /// @param basePrice    quote-units per whole token at the start of the curve
    /// @param slope        quote-units added to the price per whole token sold
    /// @return id the launch id
    function launchToken(
        string calldata name,
        string calldata symbol,
        uint256 totalSupply,
        uint256 curveSupply,
        uint256 basePrice,
        uint256 slope
    ) external returns (uint256 id) {
        Agent storage a = _agents[msg.sender];
        require(a.exists, "register first");
        require(bytes(name).length > 0 && bytes(symbol).length > 0, "name/symbol");
        require(totalSupply > 0 && curveSupply <= totalSupply, "bad supply");
        require(curveSupply == 0 || basePrice > 0, "bad price");
        require(slope == 0 || curveSupply > 0, "slope w/o curve");

        id = _launches.length;
        _launches.push();
        Launch storage L = _launches[id];

        L.id = id;
        L.token = address(new AgentToken(name, symbol, address(this)));
        L.creator = msg.sender;
        L.didHash = a.didHash;
        L.name = name;
        L.symbol = symbol;
        L.totalSupply = totalSupply;
        L.curveSupply = curveSupply;
        L.sold = 0;
        L.reserve = 0;
        L.basePrice = basePrice;
        L.slope = slope;
        L.raised = 0;
        L.graduated = curveSupply == 0;
        L.createdAt = block.timestamp;

        launchOfToken[L.token] = id + 1; // +1 so 0 means "unknown"
        _agentLaunchIds[msg.sender].push(id);
        a.launched += 1;

        // The non-curve portion is the creator's allocation, minted up front.
        uint256 creatorAlloc = totalSupply - curveSupply;
        if (creatorAlloc > 0) {
            AgentToken(L.token).mint(msg.sender, creatorAlloc * ONE_TOKEN);
        }

        emit TokenLaunched(id, L.token, msg.sender, L.didHash, symbol, totalSupply, curveSupply);
    }

    /* --------------------------------- curve -------------------------------- */

    /// @notice Cost in quote-units to buy `k` whole tokens right now.
    function quoteBuy(uint256 id, uint256 k) public view returns (uint256 cost, uint256 fee, uint256 total) {
        Launch storage L = _launches[id];
        require(L.token != address(0), "no launch");
        require(L.sold + k <= L.curveSupply, "exceeds curve");
        cost = k * L.basePrice + L.slope * (k * L.sold + (k * (k - 1)) / 2);
        fee = (cost * buyFeeBps) / 10_000;
        total = cost + fee;
    }

    /// @notice Refund in quote-units for selling `k` whole tokens right now.
    function quoteSell(uint256 id, uint256 k) public view returns (uint256 refund, uint256 fee, uint256 net) {
        Launch storage L = _launches[id];
        require(L.token != address(0), "no launch");
        require(L.sold >= k && k > 0, "exceeds sold");
        refund = k * L.basePrice + L.slope * (k * (L.sold - 1) - (k * (k - 1)) / 2);
        if (refund > L.reserve) refund = L.reserve;
        fee = (refund * sellFeeBps) / 10_000;
        net = refund - fee;
    }

    /// @notice Buy `wholeTokens` off the curve. Caller must approve `total` to this pad.
    function buy(uint256 id, uint256 wholeTokens) external returns (uint256 cost) {
        Launch storage L = _launches[id];
        require(L.token != address(0), "no launch");
        require(!L.graduated, "graduated");
        require(wholeTokens > 0, "amount=0");

        uint256 fee;
        uint256 total;
        (cost, fee, total) = quoteBuy(id, wholeTokens);
        require(quote.transferFrom(msg.sender, address(this), total), "pay failed");

        L.reserve += cost;
        L.raised += cost;
        L.sold += wholeTokens;
        if (L.sold == L.curveSupply) {
            L.graduated = true;
            emit Graduated(id, L.raised);
        }
        AgentToken(L.token).mint(msg.sender, wholeTokens * ONE_TOKEN);
        if (fee > 0) {
            require(quote.transfer(owner, fee), "fee failed");
        }
        emit Bought(id, msg.sender, wholeTokens, cost, fee);
    }

    /// @notice Sell `wholeTokens` tokens back to the curve.
    function sell(uint256 id, uint256 wholeTokens) external returns (uint256 net) {
        Launch storage L = _launches[id];
        require(L.token != address(0), "no launch");
        require(wholeTokens > 0, "amount=0");

        (uint256 refund, uint256 fee, uint256 out) = quoteSell(id, wholeTokens);
        L.sold -= wholeTokens;
        L.reserve -= refund;
        L.graduated = false;
        AgentToken(L.token).burn(msg.sender, wholeTokens * ONE_TOKEN);
        if (fee > 0) {
            require(quote.transfer(owner, fee), "fee failed");
        }
        require(quote.transfer(msg.sender, out), "refund failed");
        emit Sold(id, msg.sender, wholeTokens, refund, fee);
        net = out;
    }

    /* --------------------------------- views -------------------------------- */

    function totalAgents() external view returns (uint256) {
        return _agentList.length;
    }

    function agentAt(uint256 i) external view returns (address) {
        return _agentList[i];
    }

    function getAgent(address who)
        external
        view
        returns (bytes32 didHash, string memory name, string memory metadataURI, uint256 launched, uint256 registeredAt, bool exists)
    {
        Agent storage a = _agents[who];
        return (a.didHash, a.name, a.metadataURI, a.launched, a.registeredAt, a.exists);
    }

    function totalLaunches() external view returns (uint256) {
        return _launches.length;
    }

    function agentLaunchCount(address who) external view returns (uint256) {
        return _agentLaunchIds[who].length;
    }

    function agentLaunchIdAt(address who, uint256 i) external view returns (uint256) {
        return _agentLaunchIds[who][i];
    }

    /// @notice Full launch record (struct returned as an ABI tuple).
    function getLaunch(uint256 id) external view returns (Launch memory) {
        require(_launches[id].token != address(0), "no launch");
        return _launches[id];
    }

    /// @notice Current marginal price of the next whole token (quote-units).
    function spotPrice(uint256 id) external view returns (uint256) {
        Launch storage L = _launches[id];
        require(L.token != address(0), "no launch");
        return L.basePrice + L.slope * L.sold;
    }

    /// @notice Market cap implied by the current marginal price (whole-token terms).
    function impliedMarketCap(uint256 id) external view returns (uint256) {
        Launch storage L = _launches[id];
        require(L.token != address(0), "no launch");
        return (L.basePrice + L.slope * L.sold) * L.totalSupply;
    }

    function setFees(uint256 newBuyFeeBps, uint256 newSellFeeBps) external onlyOwner {
        require(newBuyFeeBps <= 1_000 && newSellFeeBps <= 1_000, "fee too high");
        buyFeeBps = newBuyFeeBps;
        sellFeeBps = newSellFeeBps;
        emit FeesSet(newBuyFeeBps, newSellFeeBps);
    }
}
