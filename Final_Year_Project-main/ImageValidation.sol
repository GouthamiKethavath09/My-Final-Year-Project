// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IImageDepository {
    // Updated search function returns all extended parameters.
    function search(string calldata imageId) external view returns (
        string memory originalIpfs,
        string memory logoIpfs,
        string memory watermarkIpfs,
        uint256 scramblingParamA,
        uint256 scramblingParamB,
        uint256 N,
        uint256 l,
        uint256 n,
        string memory waveletName
    );
    
    function authorizeUser(address user) external;
    function auth_user(address user) external view returns (bool);
}

contract ImageValidation {
    address public OWNER;
    IImageDepository public repository;

    struct ImageResult {
        string originalIpfs;
        string logoIpfs;
        string watermarkIpfs;
        uint256 scramblingParamA;
        uint256 scramblingParamB;
        uint256 N;
        uint256 l;
        uint256 n;
        string waveletName;
    }
    
    // Mapping by image identifier to store retrieved results
    mapping(string => ImageResult) public results;

    event Deposit(address indexed from, uint256 value);
    event SearchPerformed(
        string indexed imageId,
        string originalIpfs,
        string logoIpfs,
        string watermarkIpfs,
        uint256 scramblingParamA,
        uint256 scramblingParamB,
        uint256 N,
        uint256 l,
        uint256 n,
        string waveletName
    );

    constructor(address _repositoryAddress) {
        OWNER = msg.sender;
        repository = IImageDepository(_repositoryAddress);
    }

    // Modifier to allow only the owner or authorized users to access specific functions
    modifier onlyAuthorized() {
        require(msg.sender == OWNER || repository.auth_user(msg.sender), "Not authorized to access this function");
        _;
    }

    // Deposit function to send Ether to the contract
    function deposit() public payable returns (bool) {
        emit Deposit(msg.sender, msg.value);
        return true;
    }

    // Search function: calls the repository's search function and stores the returned data locally.
    function search(string memory imageId) public onlyAuthorized {
        (
            string memory originalIpfs,
            string memory logoIpfs,
            string memory watermarkIpfs,
            uint256 scramblingParamA,
            uint256 scramblingParamB,
            uint256 N,
            uint256 l,
            uint256 n,
            string memory waveletName
        ) = repository.search(imageId);
        results[imageId] = ImageResult(
            originalIpfs,
            logoIpfs,
            watermarkIpfs,
            scramblingParamA,
            scramblingParamB,
            N,
            l,
            n,
            waveletName
        );
        emit SearchPerformed(imageId, originalIpfs, logoIpfs, watermarkIpfs, scramblingParamA, scramblingParamB, N, l, n, waveletName);
    }

    // Get result stored in the results mapping.
    function getResult(string memory imageId) public view onlyAuthorized returns (
        string memory originalIpfs,
        string memory logoIpfs,
        string memory watermarkIpfs,
        uint256 scramblingParamA,
        uint256 scramblingParamB,
        uint256 N,
        uint256 l,
        uint256 n,
        string memory waveletName
    ) {
        ImageResult memory res = results[imageId];
        return (
            res.originalIpfs,
            res.logoIpfs,
            res.watermarkIpfs,
            res.scramblingParamA,
            res.scramblingParamB,
            res.N,
            res.l,
            res.n,
            res.waveletName
        );
    }

    // Fallback function to receive Ether
    receive() external payable {}
}
