export const proposalPlugin = {
  id: "proposal",
  name: "Proposal Draft",
  route: "/proposals",
  navigation: {
    label: "제안서 초안",
    order: 30,
  },
} as const;

export type ProposalPlugin = typeof proposalPlugin;
