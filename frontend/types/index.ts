export type Product={id:number;name:string;slug:string;description:string;price:number;image_url:string;stock:number;category_id?:number|null;is_featured:boolean};
export type CartItem={product_id:number;name:string;price:number;image_url:string;quantity:number;subtotal:number};
export type Cart={items:CartItem[];total:number};
